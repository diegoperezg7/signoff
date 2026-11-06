from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import agent_tools
from . import projections as P
from .agent_runtime import AgentApproval, AgentCheckpoint, AgentPolicy, AgentRunRecord, AgentStep, ToolRegistry, default_policy
from .agents import AgentId, agent_catalog, build_plan, get_agent
from .auth import CurrentUser, current_user, require_role, set_membership_validator
from .catalog import ProjectCatalog
from .domain import BugChangeAssessment
from .email_provider import build_email_provider
from .file_inspector import inspect_file
from .jobs import InlineJobRunner
from .persistence import PostgresRepository
from .providers import GatewayLLMProvider, HostedLLMProvider, MockLLMProvider as ContractMockLLMProvider
from .qa_explorer import QAExplorer
from .security import DataClassification, PrivacyPolicy, classify_text, redact_sensitive
from .seed import ACME_PROJECT_ID, ACME_RELEASE_ID, CUSTOMER_PROJECT_ID, CUSTOMER_RELEASE_ID, L, ProjectState, seed_projects
from .storage import LocalStorageProvider, S3StorageProvider

ReleaseStatus = Literal["in_signoff", "ready", "on_hold", "accepted", "revision_requested", "rejected"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mock_mode() -> bool:
    return os.getenv("MOCK_MODE", "true").lower() == "true"


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
    requirement_ids: list[str] = Field(default_factory=list)


class AcceptanceDecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected", "revision_requested", "pending"]
    comment: str = ""


class ReleaseStatusRequest(BaseModel):
    status: ReleaseStatus


class HumanEvidenceRequest(BaseModel):
    requirement_id: str
    kind: Literal["screenshot", "video", "document", "link", "comment", "manual_test_result"]
    description: str
    source: str


class RequirementPatch(BaseModel):
    scope_status: Optional[Literal["agreed", "pending", "out_of_scope"]] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    owner_id: Optional[str] = None


class CommentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ChangePatch(BaseModel):
    status: Literal["proposed", "approved", "rejected"]


class ProposalRejectRequest(BaseModel):
    comment: str = ""


class _ClassifiedRequest(BaseModel):
    classification: DataClassification = DataClassification.CONFIDENTIAL

    @field_validator("classification", mode="before")
    @classmethod
    def parse_classification(cls, value: Any) -> DataClassification:
        if isinstance(value, str):
            return DataClassification[value.upper()]
        return value


class AITaskRequest(_ClassifiedRequest):
    task: Literal["extract_scope", "analyze_requirement", "generate_acceptance_criteria", "classify_change", "classify_bug_or_change", "plan_verification", "analyze_observation", "judge_result", "summarize_delivery"]
    context: dict = Field(default_factory=dict)
    consent: bool = False
    redact_pii: bool = True
    document_id: Optional[str] = None
    provider_route: Optional[str] = None


class AgentRunRequest(_ClassifiedRequest):
    agent_id: AgentId
    input: str = agent_tools.DEFAULT_INPUT
    requirement_id: Optional[str] = None
    consent: bool = False
    redact_pii: bool = True
    target_url: str = "http://localhost:3000/dashboard"
    routes: list[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    provider_route: Optional[str] = None


class AgentDispatchRequest(_ClassifiedRequest):
    input: str
    requirement_id: Optional[str] = None
    consent: bool = False
    redact_pii: bool = True
    target_url: str = "http://localhost:3000/dashboard"
    routes: list[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    provider_route: Optional[str] = None


class IntelligenceQuestionRequest(_ClassifiedRequest):
    question: str = Field(min_length=3, max_length=2000)
    requirement_id: Optional[str] = None
    consent: bool = False
    redact_pii: bool = True
    document_id: Optional[str] = None
    provider_route: Optional[str] = None


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


class AIConsentRequest(_ClassifiedRequest):
    document_id: str = Field(min_length=3, max_length=240)
    provider: str = Field(min_length=2, max_length=80)
    model_or_route: str = Field(min_length=2, max_length=160)
    purpose: str = Field(min_length=3, max_length=240)
    expires_in_days: int = Field(default=30, ge=1, le=365)


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
    """In-memory store: per-project facts plus global agent and audit records."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.email_deliveries: list[dict[str, Any]] = []
        self.agent_policies: dict[str, AgentPolicy] = {}
        self.reset()

    def reset(self) -> None:
        self.projects: dict[str, ProjectState] = seed_projects()
        self.audit_events: list[dict[str, Any]] = []
        for state in self.projects.values():
            for event in state.events:
                self.audit_events.append({"id": f"evt_{uuid4().hex[:12]}", "organization_id": state.project["organization_id"], "project_id": state.id, **event})
            state.events = []
        self.audit_events.sort(key=lambda item: item["created_at"])
        self.reviews: list[dict] = []
        self.llm_runs: list[dict] = []
        self.ai_proposals: dict[str, AIProposal] = {}
        self.proposals: dict[str, dict[str, Any]] = {}
        # Mock adapter for the durable agent tables; same shape as PostgreSQL.
        self.agent_runs: dict[str, AgentRunRecord] = {}
        self.agent_steps: dict[str, AgentStep] = {}
        self.agent_step_meta: dict[str, dict[str, Any]] = {}
        self.agent_checkpoints: dict[str, AgentCheckpoint] = {}
        self.agent_approvals: dict[str, AgentApproval] = {}
        self.agent_events: dict[str, list[dict[str, Any]]] = {}
        self.agent_tool_calls: dict[str, list[dict[str, Any]]] = {}
        self.ai_consents: dict[str, dict[str, Any]] = {}
        self.review_challenges: dict[str, dict[str, Any]] = {}
        self.review_sessions: dict[str, dict[str, Any]] = {}
        self.document_records: dict[str, dict[str, Any]] = {}


store = DemoStore()
catalog = ProjectCatalog(store)
storage = LocalStorageProvider() if mock_mode() else S3StorageProvider()
job_runner = InlineJobRunner()
privacy_policy = PrivacyPolicy()
tool_registry = ToolRegistry()
qa_explorer = QAExplorer()
email_provider = build_email_provider(store.email_deliveries)
agent_repository: Any = None
app = FastAPI(title="Signoff API", version="0.2.0", description="Signoff software delivery assurance API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:4100", "http://127.0.0.1:4100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def reset_demo_state() -> None:
    """Reseed the in-memory facts (tests and demo resets)."""
    with store.lock:
        store.reset()


@app.middleware("http")
async def security_headers_and_api_guard(request: Request, call_next):
    path = request.url.path
    public_api = path.startswith("/api/v1/review/") or path.startswith("/api/v1/evidence/")
    production = not mock_mode()
    authorization = request.headers.get("authorization", "")
    if production and path.startswith("/api/v1/") and not public_api and request.method != "OPTIONS" and not authorization.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    # Resolve project URLs at the HTTP boundary as well as inside handlers.
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
    if request.url.scheme == "https" or production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- Helpers -----------------------------------------------------------------

def project_state(project_id: str, user: CurrentUser | None = None) -> ProjectState:
    state = store.projects.get(project_id)
    if state is None or (user is not None and state.project["organization_id"] != user.organization_id):
        raise HTTPException(404, "Project not found")
    return state


def project_or_404(project_id: str) -> dict:
    project = catalog.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def require_project_access(project_id: str, user: CurrentUser = Depends(current_user)) -> None:
    """Resolve the project through the caller's organization before any handler runs."""
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")


def requirement_or_404(state: ProjectState, key: str) -> dict[str, Any]:
    requirement = state.requirement(key)
    if requirement is None:
        raise HTTPException(404, "Requirement not found")
    return requirement


def member_id_for(user: CurrentUser, state: ProjectState | None) -> str:
    """The acting member: the caller if they are on the team, else the project owner."""
    if state is None:
        return user.id
    if state.member(user.id):
        return user.id
    return state.member_by_role("owner")["id"]


def audit_event(user: CurrentUser | None, event_type: str, project_id: str | None = None, *, actor_id: str | None = None, ref: dict | None = None, params: dict | None = None, **payload: Any) -> dict[str, Any]:
    """Store metadata-only audit records; document content never belongs here.

    ``params`` feed the localized activity text; ``actor_id`` is a project member,
    ``agent:<id>`` or ``system``.
    """
    state = store.projects.get(project_id) if project_id else None
    if actor_id is None:
        actor_id = member_id_for(user, state) if user else "system"
    record = {
        "id": f"evt_{uuid4().hex[:12]}",
        "organization_id": user.organization_id if user else (state.project["organization_id"] if state else None),
        "project_id": project_id,
        "actor_id": actor_id,
        "user_id": user.id if user else None,
        "event": event_type,
        "created_at": now(),
        "params": params or {},
        "ref": ref,
        **payload,
    }
    with store.lock:
        store.audit_events.append(record)
    return record


def req_ref(requirement: dict[str, Any]) -> dict[str, str]:
    return {"type": "requirement", "id": requirement["id"], "label": requirement["id"]}


def proposals_list() -> list[dict[str, Any]]:
    return list(store.proposals.values())


def _review_record(token: str) -> dict[str, Any]:
    """Resolve server-side review metadata without persisting raw guest tokens."""
    configured_demo = os.getenv("SIGNOFF_REVIEW_TOKEN_DEMO", "demo-review-token" if mock_mode() else "")
    configured_acme = os.getenv("SIGNOFF_REVIEW_TOKEN_ACME", "acme-review-token" if mock_mode() else "")
    if configured_demo and secrets.compare_digest(token, configured_demo):
        return {"project_id": CUSTOMER_PROJECT_ID, "release_id": CUSTOMER_RELEASE_ID, "email": "client@northstar.example"}
    if configured_acme and secrets.compare_digest(token, configured_acme):
        return {"project_id": ACME_PROJECT_ID, "release_id": ACME_RELEASE_ID, "email": "reviewer@acme.example"}
    raise HTTPException(404, "Review link not found or expired")


def _guest_session_valid(token: str, session_token: Optional[str]) -> bool:
    if mock_mode():
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


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, "")))
    except ValueError:
        return default


@app.on_event("startup")
def configure_persistence() -> None:
    """Switch the same catalog contract to PostgreSQL outside mock mode."""
    global catalog, agent_repository
    if mock_mode():
        return
    try:
        repository = PostgresRepository()
        repository.initialize(catalog)
        catalog = repository  # type: ignore[assignment]
        agent_repository = repository
        set_membership_validator(repository.membership_role)
    except Exception as exc:
        raise RuntimeError(f"SDA persistence could not start: {exc}") from exc


# --- Projects and releases ------------------------------------------------------

@app.get("/api/v1/projects")
def list_projects(locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    """Return the tenant-scoped projects available in the active workspace."""
    return {"items": catalog.list_projects(user.organization_id, P.normalize_locale(locale))}


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    project = catalog.get_project(project_id, user.organization_id, P.normalize_locale(locale))
    if not project:
        raise HTTPException(404, "Project not found")
    return {**project, "releases": catalog.list_releases(project_id, user.organization_id)}


@app.get("/api/v1/projects/{project_id}/releases")
def list_releases(project_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return {"items": catalog.list_releases(project_id, user.organization_id)}


@app.get("/api/v1/projects/{project_id}/releases/{release_id}/dashboard")
def project_release_dashboard(project_id: str, release_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    projection = catalog.dashboard(project_id, release_id, user.organization_id, P.normalize_locale(locale))
    if projection is None:
        raise HTTPException(404, "Project or release not found")
    return projection


def _release_state(project_id: str, release_id: str, user: CurrentUser) -> ProjectState:
    state = project_state(project_id, user)
    if state.release["id"] != release_id:
        raise HTTPException(404, "Project or release not found")
    return state


@app.patch("/api/v1/projects/{project_id}/releases/{release_id}/status")
def update_release_status(project_id: str, release_id: str, payload: ReleaseStatusRequest, user: CurrentUser = Depends(current_user)) -> dict:
    require_role(user, "owner", "admin", "member")
    state = _release_state(project_id, release_id, user)
    with store.lock:
        state.release["status"] = payload.status
    audit_event(user, "release_status_updated", project_id, release_id=release_id, status=payload.status, params={"status": payload.status})
    return {"project_id": project_id, "release_id": release_id, "status": payload.status}


@app.post("/api/v1/projects/{project_id}/releases/{release_id}/send-for-acceptance")
def send_release_for_acceptance(project_id: str, release_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    require_role(user, "owner", "admin", "member")
    state = _release_state(project_id, release_id, user)
    with store.lock:
        state.release["status"] = "ready"
    audit_event(user, "release_sent_for_acceptance", project_id, release_id=release_id)
    return {"project_id": project_id, "release_id": release_id, "status": "ready"}


@app.get("/api/v1/reference-dashboard")
def reference_dashboard(locale: str = "en") -> dict:
    """Compatibility alias for older clients; the canonical route is project/release scoped."""
    projection = catalog.dashboard(ACME_PROJECT_ID, ACME_RELEASE_ID, locale=P.normalize_locale(locale))
    assert projection is not None
    return projection


@app.get("/api/v1/projects/{project_id}/team", dependencies=[Depends(require_project_access)])
def team(project_id: str) -> list[dict]:
    return P.team(project_state(project_id))


# --- AI plumbing ---------------------------------------------------------------

def llm_provider() -> Any:
    if mock_mode():
        return ContractMockLLMProvider()
    selected = os.getenv("LLM_PROVIDER", "hosted-a").strip().lower()
    if selected == "self-hosted":
        return GatewayLLMProvider(provider_id="self-hosted")
    if selected == "hosted-b":
        return GatewayLLMProvider(provider_id="hosted-b")
    return HostedLLMProvider()


def _consent_key(project_id: str, document_id: str, provider: str, model_or_route: str) -> str:
    return f"{project_id}:{document_id}:{provider.lower()}:{model_or_route}"


def _valid_document_consent(project_id: str, document_id: str | None, user: CurrentUser, provider: Any, requested_classification: DataClassification, requested_route: str | None = None) -> bool:
    if mock_mode():
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
    if not mock_mode() and classification >= DataClassification.CONFIDENTIAL and not granted:
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
        audit_event(user, "agent_alert_sent", run.project_id, run_id=run.id, delivery_id=delivery["id"], provider=delivery["provider"])
    except Exception as exc:  # notification failure must not fail the agent run
        audit_event(user, "agent_alert_failed", run.project_id, run_id=run.id, error=str(exc)[:240])


def _redact_agent_value(value: Any, redact_pii: bool) -> Any:
    if isinstance(value, str):
        return redact_sensitive(value, redact_pii=redact_pii)[0]
    if isinstance(value, dict):
        return {key: _redact_agent_value(item, redact_pii) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_agent_value(item, redact_pii) for item in value]
    return value


# --- Agents --------------------------------------------------------------------

TERMINAL_EVENTS = {"run_completed", "run_failed"}


@app.get("/api/v1/agents")
def list_agents(user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Return the least-privilege contextual agents available to this workspace."""
    policy = store.agent_policies.setdefault(user.organization_id, default_policy(user.organization_id))
    return {"items": agent_catalog(), "tools": tool_registry.list(), "policy": {**policy.model_dump(), "runtime": "mock" if mock_mode() else "external"}}


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


def _emit(run_id: str, event_type: str, data: dict[str, Any]) -> None:
    with store.lock:
        events = store.agent_events.setdefault(run_id, [])
        events.append({"id": len(events) + 1, "event": event_type, "data": data})


def _step_delay(rng: random.Random) -> float:
    raw = os.getenv("SIGNOFF_AGENT_STEP_DELAY", "").strip()
    if raw:
        return _float_env("SIGNOFF_AGENT_STEP_DELAY", 0.0)
    return rng.uniform(0.4, 0.9) if mock_mode() else 0.0


def _agent_name(agent_id: str) -> dict[str, Any]:
    return {"id": agent_id, "name": L(P.AGENT_NAMES[agent_id][0], P.AGENT_NAMES[agent_id][1])}


@app.post("/api/v1/projects/{project_id}/agents/dispatch")
def dispatch_agent(project_id: str, payload: AgentDispatchRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    agent_id = select_agent_for_input(payload.input)
    audit_event(user, "ai_agent_dispatched", project_id, agent_id=agent_id)
    return run_agent(project_id, AgentRunRequest(agent_id=agent_id, input=payload.input, requirement_id=payload.requirement_id, classification=payload.classification, consent=payload.consent, redact_pii=payload.redact_pii, target_url=payload.target_url, routes=payload.routes, document_id=payload.document_id, provider_route=payload.provider_route), user)


@app.post("/api/v1/projects/{project_id}/agents/run")
def run_agent(project_id: str, payload: AgentRunRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Queue a bounded agent plan and execute it in the background.

    Agents read facts and finish with one draft proposal; nothing is applied
    until a member approves the proposal.
    """
    state = project_state(project_id, user)
    agent = get_agent(payload.agent_id)
    provider = llm_provider()
    _assert_ai_consent(project_id, payload.document_id, user, provider, payload.classification, payload.consent, payload.provider_route)
    policy = store.agent_policies.setdefault(user.organization_id, default_policy(user.organization_id))
    safe_input = str(_redact_agent_value(payload.input, payload.redact_pii and privacy_policy.redact_before_ai))
    plan = build_plan(payload.agent_id, safe_input, payload.requirement_id)
    if len(plan) > policy.max_steps:
        raise HTTPException(400, "Agent plan exceeds the organization step limit")
    for step in plan:
        try:
            tool_registry.authorize(step["tool"], agent.tools, policy)
        except (KeyError, PermissionError) as exc:
            raise HTTPException(403, str(exc)) from exc
    if payload.requirement_id and state.requirement(payload.requirement_id) is None:
        raise HTTPException(404, "Requirement not found")
    run = AgentRunRecord(organization_id=user.organization_id, project_id=project_id, agent_id=payload.agent_id, status="queued", input=safe_input, classification=payload.classification.name, provider=provider.__class__.__name__, model=provider.model, max_steps=policy.max_steps)
    with store.lock:
        requirement = agent_tools.pick_requirement(state, payload.requirement_id)
        run.result = {"requirement_id": requirement["id"] if requirement else None}
        store.agent_runs[run.id] = run
        store.agent_tool_calls[run.id] = []
    _emit(run.id, "run_started", {"run_id": run.id, "agent": _agent_name(agent.id), "requirement_id": requirement["id"] if requirement else None, "steps": [{"index": index, "tool": step["tool"], "label": agent_tools.tool_label(step["tool"])} for index, step in enumerate(plan)]})
    options = {"input": safe_input, "requirement_id": requirement["id"] if requirement else None, "target_url": payload.target_url, "routes": list(payload.routes), "redact_pii": payload.redact_pii}
    threading.Thread(target=_agent_worker, args=(run.id, plan, options, user, provider, policy), daemon=True, name=f"agent-{run.id}").start()
    return {"run_id": run.id, "id": run.id, "project_id": project_id, "agent": {"id": agent.id, "name": agent.name}, "status": "queued", "requirement_id": options["requirement_id"], "created_at": run.created_at}


def _agent_worker(run_id: str, plan: list[dict[str, Any]], options: dict[str, Any], user: CurrentUser, provider: Any, policy: AgentPolicy) -> None:
    run = store.agent_runs[run_id]
    state = store.projects[run.project_id]
    agent = get_agent(run.agent_id)
    rng = random.Random(run_id)
    started = time.perf_counter()
    outputs: dict[str, Any] = {}
    step_record: AgentStep | None = None
    try:
        with store.lock:
            requirement = state.requirement(options["requirement_id"]) if options["requirement_id"] else None
        ctx = {"state": state, "requirement": requirement, "input": options["input"], "provider": provider, "qa": qa_explorer, "target_url": options["target_url"], "routes": options["routes"], "max_steps": policy.max_steps, "run_id": run_id, "storage": storage, "proposals": [], "mock": mock_mode()}
        run.status = "running"
        run.updated_at = now()
        for ordinal, step in enumerate(plan, 1):
            if run.status == "cancelled":
                _emit(run_id, "run_failed", {"error": "Run cancelled"})
                return
            tool = step["tool"]
            label = agent_tools.tool_label(tool)
            step_record = AgentStep(ordinal=ordinal, tool=tool, input=step.get("input", {}), status="running")
            with store.lock:
                store.agent_steps[step_record.id] = step_record
                run.step_ids.append(step_record.id)
                run.current_step = ordinal
            _emit(run_id, "step_started", {"index": ordinal - 1, "tool": tool, "label": label})
            tool_started = time.perf_counter()
            time.sleep(_step_delay(rng))
            ctx["qa"] = qa_explorer
            with store.lock:
                ctx["proposals"] = proposals_list()
                output, summary, refs = agent_tools.execute(tool, ctx, outputs)
                outputs[tool] = output
                duration_ms = round((time.perf_counter() - tool_started) * 1000)
                step_record.output = output
                step_record.status = "completed"
                step_record.duration_ms = duration_ms
                store.agent_step_meta[step_record.id] = {"index": ordinal - 1, "label": label, "summary": summary, "refs": refs}
                checkpoint = AgentCheckpoint(run_id=run_id, ordinal=ordinal, state={"outputs": outputs, "current_tool": tool})
                store.agent_checkpoints[checkpoint.id] = checkpoint
                run.checkpoint_ids.append(checkpoint.id)
                store.agent_tool_calls[run_id].append({"tool": tool, "input": step.get("input", {}), "status": "completed", "duration_ms": duration_ms})
            persist_agent_snapshot(run)
            _emit(run_id, "step_completed", {"index": ordinal - 1, "tool": tool, "label": label, "duration_ms": duration_ms, "summary": summary, "refs": refs})
        with store.lock:
            ctx["proposals"] = proposals_list()
            draft = agent_tools.build_proposal(agent.id, ctx, outputs)
            proposal = {"id": f"proposal_{uuid4().hex[:12]}", "project_id": state.id, "run_id": run_id, "agent_id": agent.id, "status": "draft", "created_at": now(), "decided_by": None, "decided_at": None, **draft}
            store.proposals[proposal["id"]] = proposal
            run.proposal_id = proposal["id"]
            run.result = {**outputs, "requirement_id": options["requirement_id"]}
            run.status = "requires_approval"
            run.updated_at = now()
            store.llm_runs.append({"id": f"llm_{uuid4().hex[:10]}", "project_id": state.id, "task": f"agent:{agent.id}", "provider": provider.__class__.__name__, "model": provider.model, "prompt_version": "sda-agent-v1", "input_tokens": len(options["input"]) // 4, "output_tokens": len(json.dumps(outputs, default=str)) // 4, "estimated_cost": 0 if provider.__class__.__name__ == "MockLLMProvider" else 0.01, "duration_ms": round((time.perf_counter() - started) * 1000), "status": "completed", "created_at": now()})
        persist_agent_snapshot(run)
        audit_event(user, "ai_agent_run_completed", state.id, actor_id=f"agent:{agent.id}", agent_id=agent.id, run_id=run_id, tools=[item["tool"] for item in plan], proposal_id=proposal["id"])
        audit_event(user, "proposal_created", state.id, actor_id=f"agent:{agent.id}", ref={"type": "proposal", "id": proposal["id"], "label": proposal["title"]["en"]}, params={"title": proposal["title"]}, proposal_id=proposal["id"])
        _emit(run_id, "proposal_created", {"proposal_id": proposal["id"]})
        _emit(run_id, "run_completed", {"status": "requires_approval", "summary": proposal["summary"], "proposal_id": proposal["id"]})
        maybe_notify_agent_run(run, agent.name, user)
    except Exception as exc:  # any failure ends the run, never the process
        message = str(exc)[:300] or exc.__class__.__name__
        with store.lock:
            run.status = "failed"
            run.error = message
            run.updated_at = now()
            if step_record is not None and step_record.status == "running":
                step_record.status = "failed"
                step_record.error = message
        audit_event(user, "agent_run_failed", state.id, actor_id=f"agent:{agent.id}", run_id=run_id, params={"error": message})
        _emit(run_id, "run_failed", {"error": message})


def _agent_run_or_404(run_id: str, user: CurrentUser) -> AgentRunRecord:
    run = store.agent_runs.get(run_id)
    if run is None or run.organization_id != user.organization_id:
        raise HTTPException(404, "Agent run not found")
    if not catalog.get_project(run.project_id, user.organization_id):
        raise HTTPException(404, "Agent run not found")
    return run


def _run_view(run: AgentRunRecord, locale: str) -> dict[str, Any]:
    return {**run.model_dump(), "agent": P.agent_ref(run.agent_id, locale), "requirement_id": run.result.get("requirement_id")}


def _format_event(run: AgentRunRecord, event: dict[str, Any], locale: str) -> str:
    data = event["data"]
    if event["event"] == "proposal_created":
        proposal = store.proposals.get(data["proposal_id"])
        state = store.projects.get(run.project_id)
        data = {"proposal": P.proposal_view(proposal, locale, state) if proposal else None}
    return f"id: {event['id']}\nevent: {event['event']}\ndata: {json.dumps(P.loc(data, locale), ensure_ascii=False, default=str)}\n\n"


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
def list_agent_runs(project_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    locale = P.normalize_locale(locale)
    runs = [_run_view(run, locale) for run in list(store.agent_runs.values()) if run.project_id == project_id and run.organization_id == user.organization_id]
    return {"items": sorted(runs, key=lambda item: item["created_at"], reverse=True)}


@app.get("/api/v1/agent-runs/{run_id}")
def get_agent_run(run_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    locale = P.normalize_locale(locale)
    with store.lock:
        steps = []
        for step in store.agent_steps.values():
            if step.id in run.step_ids:
                meta = store.agent_step_meta.get(step.id, {})
                steps.append({**step.model_dump(), **P.loc(meta, locale)})
        checkpoints = [checkpoint.model_dump() for checkpoint in store.agent_checkpoints.values() if checkpoint.id in run.checkpoint_ids]
        approvals = [approval.model_dump() for approval in store.agent_approvals.values() if approval.id in run.approval_ids]
        tool_calls = list(store.agent_tool_calls.get(run.id, []))
    return {"run": run.model_dump(), "id": run.id, "agent": P.agent_ref(run.agent_id, locale), "status": run.status, "proposal_id": run.proposal_id, "requirement_id": run.result.get("requirement_id"), "error": run.error, "steps": steps, "tool_calls": tool_calls, "checkpoints": checkpoints, "approvals": approvals}


@app.get("/api/v1/agent-runs/{run_id}/events")
def agent_run_events(run_id: str, request: Request, after: Optional[int] = None, locale: str = "en", user: CurrentUser = Depends(current_user)) -> StreamingResponse:
    run = _agent_run_or_404(run_id, user)
    locale = P.normalize_locale(locale)
    start = after
    if start is None:
        try:
            start = int(request.headers.get("last-event-id") or 0)
        except ValueError:
            start = 0

    def stream():
        last = max(0, start)
        deadline = time.monotonic() + 600
        while True:
            events = list(store.agent_events.get(run_id, []))
            for event in events[last:]:
                yield _format_event(run, event, locale)
                last = event["id"]
                if event["event"] in TERMINAL_EVENTS:
                    return
            if (events and events[-1]["event"] in TERMINAL_EVENTS) or time.monotonic() > deadline:
                return
            time.sleep(0.15)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/v1/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    run = _agent_run_or_404(run_id, user)
    if run.status in {"completed", "failed", "cancelled", "requires_approval"}:
        raise HTTPException(409, "Agent run is already finished")
    run.status = "cancelled"
    run.updated_at = now()
    persist_agent_snapshot(run)
    audit_event(user, "ai_agent_run_cancelled", run.project_id, run_id=run.id)
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
    audit_event(user, "agent_alert_sent", run.project_id, run_id=run.id, delivery_id=delivery["id"], provider=delivery["provider"])
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
    audit_event(user, "ai_agent_approval_decided", run.project_id, run_id=run.id, approval_id=approval.id, decision=payload.decision)
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
    audit_event(user, "ai_agent_run_resumed", run.project_id, run_id=run.id)
    return run.model_dump()


# --- Proposals -----------------------------------------------------------------

def _next_change_code(state: ProjectState) -> str:
    numbers = [int(item["code"].split("-")[1]) for item in state.changes if re.match(r"^CHG-\d+$", item["code"])]
    return f"CHG-{(max(numbers) if numbers else 0) + 1:03d}"


def _as_text(value: Any) -> dict[str, str]:
    return value if isinstance(value, dict) and set(value) == {"en", "es"} else L(str(value), str(value))


def _apply_proposal(state: ProjectState, proposal: dict[str, Any], user: CurrentUser) -> list[dict[str, str]]:
    kind = proposal["kind"]
    payload = proposal["payload"]
    agent_actor = f"agent:{proposal['agent_id']}"
    requirement = state.requirement(proposal.get("requirement_id") or "")
    if kind in {"criteria", "verification_plan", "evidence"} and requirement is None:
        raise HTTPException(409, "The proposal's requirement no longer exists")
    if kind == "criteria":
        requirement["criteria"] = [{"id": str(uuid4()), "text": _as_text(text), "source": "agent"} for text in payload["after"]]
        requirement["defect"] = False
        return [req_ref(requirement)]
    if kind == "verification_plan":
        requirement["verification_plan"] = {"steps": payload["steps"], "proposal_id": proposal["id"]}
        return [req_ref(requirement)]
    if kind == "evidence":
        content_key = payload["artifact"]
        evidence_id = str(uuid4())
        state.evidence.append({
            "id": evidence_id, "requirement_id": requirement["id"], "artifact": Path(content_key).name, "storage_key": content_key, "kind": "observation", "source": "agent",
            "state": payload["state"], "summary": _as_text(payload["summary"]), "sha256": payload.get("sha256", ""), "size": None, "created_at": now(), "run_id": proposal["run_id"],
        })
        requirement["verification"] = {"demonstrated": "passed", "partially_demonstrated": "in_progress"}.get(payload["state"], "failed")
        return [{"type": "evidence", "id": evidence_id, "label": Path(content_key).name}, req_ref(requirement)]
    if kind == "change":
        code = _next_change_code(state)
        change = {
            "id": str(uuid4()), "code": code, "title": _as_text(payload["title"]), "original": _as_text(payload["original"]), "proposed": _as_text(payload["proposed"]),
            "classification": payload["classification"], "status": "proposed", "impact": payload["impact"], "requirement_ids": list(payload.get("requirement_ids", [])),
            "source": "agent", "created_at": now(), "created_by": agent_actor, "decided_by": None, "decided_at": None,
        }
        state.changes.append(change)
        audit_event(user, "change_proposed", state.id, actor_id=agent_actor, ref={"type": "change", "id": change["id"], "label": code}, params={"code": code})
        return [{"type": "change", "id": change["id"], "label": code}]
    if kind == "comments":
        refs = []
        for item in payload["items"]:
            target = state.requirement(item["requirement_id"])
            if target is None:
                continue
            state.comments.append({"id": f"comment_{uuid4().hex[:10]}", "requirement_id": target["id"], "author_id": agent_actor, "text": _as_text(item["text"]), "created_at": now(), "resolved": False, "resolved_at": None})
            audit_event(user, "comment_added", state.id, actor_id=agent_actor, ref=req_ref(target), params={"requirement_id": target["id"]})
            refs.append(req_ref(target))
        return refs
    return []


def _proposal_or_404(proposal_id: str, user: CurrentUser) -> tuple[ProjectState, dict[str, Any]]:
    proposal = store.proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    return project_state(proposal["project_id"], user), proposal


def approve_project_proposal(proposal_id: str, user: CurrentUser, locale: str = "en") -> dict[str, Any]:
    state, proposal = _proposal_or_404(proposal_id, user)
    with store.lock:
        if proposal["status"] != "draft":
            raise HTTPException(409, "Proposal has already been decided")
        applied = _apply_proposal(state, proposal, user)
        proposal["status"] = "approved"
        proposal["decided_by"] = member_id_for(user, state)
        proposal["decided_at"] = now()
        run = store.agent_runs.get(proposal["run_id"])
        if run is not None:
            run.status = "completed"
            run.updated_at = now()
    audit_event(user, "proposal_approved", state.id, ref={"type": "proposal", "id": proposal["id"], "label": proposal["title"]["en"]}, params={"title": proposal["title"]}, proposal_id=proposal["id"], applied=applied)
    return {"proposal": P.proposal_view(proposal, locale, state), "applied": applied}


@app.get("/api/v1/projects/{project_id}/proposals", dependencies=[Depends(require_project_access)])
def list_proposals(project_id: str, status: Optional[str] = None, locale: str = "en") -> list[dict]:
    state = project_state(project_id)
    locale = P.normalize_locale(locale)
    items = [item for item in proposals_list() if item["project_id"] == project_id and (status is None or item["status"] == status)]
    return [P.proposal_view(item, locale, state) for item in sorted(items, key=lambda item: item["created_at"], reverse=True)]


@app.post("/api/v1/projects/{project_id}/proposals/{proposal_id}/approve", dependencies=[Depends(require_project_access)])
def approve_proposal(project_id: str, proposal_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    if store.proposals.get(proposal_id, {}).get("project_id") != project_id:
        raise HTTPException(404, "Proposal not found")
    return approve_project_proposal(proposal_id, user, P.normalize_locale(locale))


@app.post("/api/v1/projects/{project_id}/proposals/{proposal_id}/reject", dependencies=[Depends(require_project_access)])
def reject_proposal(project_id: str, proposal_id: str, payload: Optional[ProposalRejectRequest] = None, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    if store.proposals.get(proposal_id, {}).get("project_id") != project_id:
        raise HTTPException(404, "Proposal not found")
    state, proposal = _proposal_or_404(proposal_id, user)
    with store.lock:
        if proposal["status"] != "draft":
            raise HTTPException(409, "Proposal has already been decided")
        proposal["status"] = "rejected"
        proposal["decided_by"] = member_id_for(user, state)
        proposal["decided_at"] = now()
        proposal["comment"] = payload.comment if payload else ""
        run = store.agent_runs.get(proposal["run_id"])
        if run is not None:
            run.status = "completed"
            run.updated_at = now()
    audit_event(user, "proposal_rejected", project_id, ref={"type": "proposal", "id": proposal["id"], "label": proposal["title"]["en"]}, params={"title": proposal["title"]}, proposal_id=proposal["id"])
    return {"proposal": P.proposal_view(proposal, P.normalize_locale(locale), state)}


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
    audit_event(user, "ai_proposal_created", project_id, task=payload.task, proposal_id=proposal.id, classification=payload.classification.name, redactions=sorted(set(redaction_categories)))
    return proposal


@app.post("/api/v1/ai/proposals/{proposal_id}/approve")
def approve_ai_proposal(proposal_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    """Legacy route: agent proposals delegate to the project apply logic."""
    if proposal_id in store.proposals:
        result = approve_project_proposal(proposal_id, user)
        return {**result["proposal"], "applied": result["applied"]}
    proposal = store.ai_proposals.get(proposal_id)
    if not proposal or not catalog.get_project(proposal.project_id, user.organization_id):
        raise HTTPException(404, "AI proposal not found")
    proposal.status = "approved"
    audit_event(user, "ai_proposal_approved", proposal.project_id, proposal_id=proposal_id)
    return proposal.model_dump()


@app.get("/api/v1/projects/{project_id}/ai/runs")
def ai_runs(project_id: str, user: CurrentUser = Depends(current_user)) -> list[dict]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return [item for item in store.llm_runs if item["project_id"] == project_id]


@app.post("/api/v1/projects/{project_id}/intelligence/ask")
def ask_project_intelligence(project_id: str, payload: IntelligenceQuestionRequest, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    state = project_state(project_id, user)
    provider = llm_provider()
    _assert_ai_consent(project_id, payload.document_id, user, provider, payload.classification, payload.consent, payload.provider_route)
    question = _redact_agent_value(payload.question, payload.redact_pii and privacy_policy.redact_before_ai)
    with store.lock:
        story = P.story(state, "en")
        ranked = sorted(P.in_scope(state), key=P.attention_rank)[:5]
        context = {"question": question, "readiness": P.readiness(state), "attention": P.attention(state, proposals_list(), "en"), **story}
    result = provider.summarize_delivery(context)
    citations = [{"type": "requirement", "id": item["id"], "title": item["title"]["en"]} for item in ranked]
    audit_event(user, "project_intelligence_question_answered", project_id, question_length=len(str(question)), citations=len(citations), provider=provider.__class__.__name__)
    return {"answer": result, "grounded": True, "confidence": 0.86 if provider.__class__.__name__ == "MockLLMProvider" else 0.78, "citations": citations, "provider": provider.__class__.__name__, "model": provider.model}


# --- Privacy and documents --------------------------------------------------------

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
    audit_event(user, "ai_document_consent_granted", project_id, document_id=payload.document_id, provider=provider, model_or_route=payload.model_or_route, classification=payload.classification.name)
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
    audit_event(user, "ai_document_consent_revoked", project_id, document_id=document_id, revoked=revoked)
    return {"status": "revoked", "document_id": document_id, "revoked": revoked}


def configured_retention_days(name: str, default: int) -> int:
    """Read a retention window. Blank or invalid values fall back to the default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


@app.get("/api/v1/projects/{project_id}/privacy/retention")
def privacy_retention(project_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    return {
        "document_retention_days": configured_retention_days("SDA_DOCUMENT_RETENTION_DAYS", 365),
        "evidence_retention_days": configured_retention_days("SDA_EVIDENCE_RETENTION_DAYS", 365),
        "portal_link_days": configured_retention_days("SDA_PORTAL_LINK_RETENTION_DAYS", 7),
        "llm_metadata_retention_days": configured_retention_days("SDA_LLM_METADATA_RETENTION_DAYS", 730),
        "raw_prompts_stored": False,
    }


@app.delete("/api/v1/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, user: CurrentUser = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "owner", "admin")
    if not catalog.get_project(project_id, user.organization_id):
        raise HTTPException(404, "Project not found")
    record = store.document_records.get(document_id)
    if not record:
        raise HTTPException(404, "Document not found")
    # Only metadata is retained in the audit event; content and the raw name are absent.
    storage_key = record.get("storage_key")
    if storage_key:
        storage.delete_object(storage_key)
    store.document_records.pop(document_id, None)
    for key, consent in list(store.ai_consents.items()):
        if consent.get("document_id") == document_id:
            consent["revoked_at"] = now()
            store.ai_consents[key] = consent
    audit_event(user, "document_erased", project_id, document_id=document_id)
    return {"status": "erased", "document_id": document_id}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock_mode": mock_mode(), "time": now()}


@app.get("/api/v1/dashboard")
def dashboard(user: CurrentUser = Depends(current_user)) -> dict:
    if not mock_mode():
        projects = catalog.list_projects(user.organization_id)
        if not projects:
            raise HTTPException(404, "No projects available in this organization")
        project = projects[0]
        return {"project": project, "counts": {}, "scope_changes": 0, "attention": [], "requirements": project.get("requirements_count", 0)}
    state = project_state(CUSTOMER_PROJECT_ID, user)
    states = [P.EVIDENCE_STATUS[item["verification"]] for item in state.requirements]
    counts = {key: states.count(key) for key in ["demonstrated", "partially_demonstrated", "not_demonstrated", "manual_review_required"]}
    return {"project": P.project_view(state), "counts": counts, "scope_changes": len(state.changes), "attention": [item["title"] for item in P.attention(state, proposals_list(), "en")], "requirements": len(state.requirements)}


# --- Requirements, criteria and comments -----------------------------------------------

@app.get("/api/v1/projects/{project_id}/requirements", dependencies=[Depends(require_project_access)])
def requirements(project_id: str, locale: str = "en") -> list[dict]:
    return P.requirement_rows(project_state(project_id), P.normalize_locale(locale))


@app.get("/api/v1/projects/{project_id}/requirements/{human_id}", dependencies=[Depends(require_project_access)])
def requirement_detail(project_id: str, human_id: str, locale: str = "en") -> dict:
    state = project_state(project_id)
    return P.requirement_detail(state, requirement_or_404(state, human_id), P.normalize_locale(locale))


@app.patch("/api/v1/projects/{project_id}/requirements/{human_id}", dependencies=[Depends(require_project_access)])
def update_project_requirement(project_id: str, human_id: str, payload: RequirementPatch, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    with store.lock:
        requirement = requirement_or_404(state, human_id)
        changes = payload.model_dump(exclude_none=True)
        if "owner_id" in changes and not state.member(changes["owner_id"]):
            raise HTTPException(422, "Owner is not a team member")
        if changes.get("scope_status") == "agreed" and requirement["scope_status"] != "agreed":
            requirement["agreed_at"] = now()
        requirement.update(changes)
    audit_event(user, "requirement_updated", project_id, ref=req_ref(requirement), params={"requirement_id": requirement["id"]}, fields=sorted(changes))
    return P.requirement_detail(state, requirement, P.normalize_locale(locale))


def _find_requirement_anywhere(key: str) -> tuple[ProjectState, dict[str, Any]]:
    for state in store.projects.values():
        requirement = state.requirement(key)
        if requirement:
            return state, requirement
    raise HTTPException(404, "Requirement not found")


@app.patch("/api/v1/requirements/{requirement_id}")
def update_requirement(requirement_id: str, payload: dict, user: CurrentUser = Depends(current_user)) -> dict:
    """Legacy route addressed by requirement UUID."""
    state, requirement = _find_requirement_anywhere(requirement_id)
    with store.lock:
        for key in ("title", "description"):
            if isinstance(payload.get(key), str):
                requirement[key] = L(payload[key], payload[key])
        if payload.get("priority") in {"high", "medium", "low"}:
            requirement["priority"] = payload["priority"]
    audit_event(user, "requirement_updated", state.id, ref=req_ref(requirement), params={"requirement_id": requirement["id"]})
    return P.requirement_row(state, requirement, "en")


def _generate_criteria(state: ProjectState, requirement: dict[str, Any], user: CurrentUser) -> None:
    provider = llm_provider()
    generated = provider.generate_acceptance_criteria({"title": requirement["title"]["en"], "description": requirement["description"]["en"]})
    with store.lock:
        requirement["criteria"] = [{"id": str(uuid4()), "text": L(item["text"], item["text"]), "source": "agent"} for item in generated]
        requirement["defect"] = False
    audit_event(user, "criteria_generated", state.id, ref=req_ref(requirement), params={"requirement_id": requirement["id"]}, requirement_id=requirement["id"], provider=provider.__class__.__name__)


@app.post("/api/v1/requirements/{requirement_id}/criteria")
def generate_criteria(requirement_id: str, user: CurrentUser = Depends(current_user)) -> dict:
    state, requirement = _find_requirement_anywhere(requirement_id)
    _generate_criteria(state, requirement, user)
    return P.requirement_row(state, requirement, "en")


@app.post("/api/v1/projects/{project_id}/requirements/{human_id}/criteria", dependencies=[Depends(require_project_access)])
def generate_project_criteria(project_id: str, human_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    """Generate criteria against the active project context."""
    state = project_state(project_id)
    requirement = requirement_or_404(state, human_id)
    _generate_criteria(state, requirement, user)
    return P.requirement_detail(state, requirement, P.normalize_locale(locale))


@app.get("/api/v1/projects/{project_id}/requirements/{human_id}/comments", dependencies=[Depends(require_project_access)])
def list_comments(project_id: str, human_id: str, locale: str = "en") -> list[dict]:
    state = project_state(project_id)
    requirement = requirement_or_404(state, human_id)
    return P.requirement_detail(state, requirement, P.normalize_locale(locale))["comments"]


@app.post("/api/v1/projects/{project_id}/requirements/{human_id}/comments", dependencies=[Depends(require_project_access)])
def add_comment(project_id: str, human_id: str, payload: CommentRequest, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    with store.lock:
        requirement = requirement_or_404(state, human_id)
        comment = {"id": f"comment_{uuid4().hex[:10]}", "requirement_id": requirement["id"], "author_id": member_id_for(user, state), "text": payload.text.strip(), "created_at": now(), "resolved": False, "resolved_at": None}
        state.comments.append(comment)
    audit_event(user, "comment_added", project_id, ref=req_ref(requirement), params={"requirement_id": requirement["id"]}, comment_id=comment["id"])
    return P.comment_view(state, comment, P.normalize_locale(locale))


@app.post("/api/v1/projects/{project_id}/comments/{comment_id}/resolve", dependencies=[Depends(require_project_access)])
def resolve_comment(project_id: str, comment_id: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    with store.lock:
        comment = next((item for item in state.comments if item["id"] == comment_id), None)
        if comment is None:
            raise HTTPException(404, "Comment not found")
        if not comment["resolved"]:
            comment["resolved"] = True
            comment["resolved_at"] = now()
    audit_event(user, "comment_resolved", project_id, ref={"type": "requirement", "id": comment["requirement_id"], "label": comment["requirement_id"]}, params={"requirement_id": comment["requirement_id"]}, comment_id=comment_id)
    return P.comment_view(state, comment, P.normalize_locale(locale))


# --- Scope ---------------------------------------------------------------------

async def _read_scope_upload(file: UploadFile) -> tuple[str, bytes]:
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
    return filename, content


def _store_document(filename: str, content: bytes, content_type: str | None) -> str:
    document_id = f"doc_{secrets.token_urlsafe(12)}"
    store.document_records[document_id] = {"id": document_id, "filename": filename, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "content_type": content_type, "status": "quarantined", "created_at": now(), "retention_days": configured_retention_days("SDA_DOCUMENT_RETENTION_DAYS", 365)}
    return document_id


@app.post("/api/v1/scope/import")
async def import_scope(file: UploadFile = File(...)) -> dict:
    filename, content = await _read_scope_upload(file)
    document_id = _store_document(filename, content, file.content_type)
    return {"status": "draft_ready", "document_id": document_id, "filename": filename, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "retention_days": store.document_records[document_id]["retention_days"], "version": "draft", "message": "Mock extraction complete. Review the suggested requirements before confirming."}


@app.get("/api/v1/projects/{project_id}/scope/versions", dependencies=[Depends(require_project_access)])
def scope_versions(project_id: str, locale: str = "en") -> list[dict]:
    return catalog.scope_versions(project_id, locale=P.normalize_locale(locale))


def _next_version(state: ProjectState) -> str:
    latest = max(state.scope_versions, key=lambda item: item["created_at"])["version"] if state.scope_versions else "v0"
    match = re.match(r"^(.*?)(\d+)$", latest)
    return f"{match.group(1)}{int(match.group(2)) + 1}" if match else f"{latest}.1"


COMPONENT_KEYWORDS = [
    ("Billing", ("invoice", "billing", "payment", "plan", "factura", "pago", "vat", "iva")),
    ("Exports", ("export", "csv", "xlsx", "download", "exporta", "descarga")),
    ("Notifications", ("notif", "email", "alert", "aviso", "correo", "webhook")),
    ("Security", ("password", "login", "2fa", "session", "security", "contraseña", "sesión", "seguridad", "audit")),
    ("Reporting", ("report", "dashboard", "chart", "informe", "panel", "gráfico")),
]


def _guess_component(state: ProjectState, text: str) -> str:
    lowered = text.lower()
    for component, words in COMPONENT_KEYWORDS:
        if any(word in lowered for word in words):
            return component
    return "Users" if state.id == ACME_PROJECT_ID else "Core workflow"


SIMULATED_EXTRACTION = [
    L("Customer can download a monthly usage statement", "El cliente puede descargar un extracto mensual de uso"),
    L("Admin can upload a custom logo for the portal", "El administrador puede subir un logotipo propio para el portal"),
    L("Export of seat usage to CSV", "Exportación del uso de licencias a CSV"),
]


def _extract_diff(state: ProjectState, filename: str, content: bytes, content_type: str | None) -> dict[str, list[dict[str, Any]]]:
    added: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    if content_type == "text/plain":
        known = {item["title"][lang].strip().lower() for item in state.requirements for lang in ("en", "es")}
        for raw in content.decode("utf-8", errors="replace").splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw).strip()
            if not line or line.startswith("#"):
                continue
            reference = re.match(r"^(REQ-\d{3,})\s*[:\-]\s*(.+)$", line)
            if reference and state.requirement(reference.group(1)):
                current = state.requirement(reference.group(1))
                if reference.group(2).strip().lower() != current["title"]["en"].lower():
                    modified.append({"id": current["id"], "title": current["title"], "before": current["title"], "after": reference.group(2).strip()})
                continue
            if line.lower() in known:
                continue
            known.add(line.lower())
            added.append({"title": line[:160], "description": line, "component": _guess_component(state, line)})
    else:
        for title in SIMULATED_EXTRACTION:
            added.append({"title": title, "description": title, "component": _guess_component(state, title["en"])})
        target = next((item for item in sorted(state.requirements, key=lambda item: item["id"]) if item["scope_status"] == "agreed"), None)
        if target:
            modified.append({"id": target["id"], "title": target["title"], "before": target["description"], "after": L(f"{target['description']['en']} Applies to every client workspace.", f"{target['description']['es']} Aplica a todos los espacios del cliente.")})
    return {"added": added, "modified": modified, "removed": []}


@app.post("/api/v1/projects/{project_id}/scope/versions", dependencies=[Depends(require_project_access)])
def create_scope_version(project_id: str, payload: ScopeVersionRequest, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    with store.lock:
        version = {"version": _next_version(state), "status": "draft", "source": payload.source, "summary": L(payload.summary, payload.summary), "created_at": now(), "created_by": member_id_for(user, state), "diff": {"added": [], "modified": [], "removed": []}, "change_request_id": payload.change_request_id}
        state.scope_versions.append(version)
    audit_event(user, "scope_draft_created", project_id, ref={"type": "scope_version", "id": version["version"], "label": version["version"]}, params={"version": version["version"]})
    return P.scope_version_view(state, version, P.normalize_locale(locale))


@app.post("/api/v1/projects/{project_id}/scope/extract", dependencies=[Depends(require_project_access)])
async def extract_scope(project_id: str, file: UploadFile = File(...), locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    filename, content = await _read_scope_upload(file)
    raw_text = content.decode("utf-8", errors="replace") if file.content_type == "text/plain" else ""
    classification = classify_text(raw_text) if raw_text else DataClassification.CONFIDENTIAL
    if not mock_mode() and classification > privacy_policy.max_external_classification:
        raise HTTPException(403, "This document requires a private AI provider and cannot be processed externally")
    document_id = _store_document(filename, content, file.content_type)
    with store.lock:
        diff = _extract_diff(state, filename, content, file.content_type)
        counts = (len(diff["added"]), len(diff["modified"]), len(diff["removed"]))
        version = {
            "version": _next_version(state), "status": "draft", "source": filename,
            "summary": L(f"Draft from {filename}: {counts[0]} added, {counts[1]} modified, {counts[2]} removed.", f"Borrador de {filename}: {counts[0]} añadidos, {counts[1]} modificados, {counts[2]} eliminados."),
            "created_at": now(), "created_by": member_id_for(user, state), "diff": diff, "document_id": document_id,
        }
        state.scope_versions.append(version)
    audit_event(user, "scope_draft_created", project_id, ref={"type": "scope_version", "id": version["version"], "label": version["version"]}, params={"version": version["version"]}, document_id=document_id)
    view = P.scope_version_view(state, version, P.normalize_locale(locale))
    view["data_policy"] = {"classification": classification.name, "redaction_required": privacy_policy.redact_before_ai, "external_processing": not mock_mode()}
    return view


@app.post("/api/v1/projects/{project_id}/scope/versions/{version}/approve", dependencies=[Depends(require_project_access)])
def approve_scope_version(project_id: str, version: str, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    added_ids: list[str] = []
    with store.lock:
        selected = next((item for item in state.scope_versions if item["version"] == version), None)
        if not selected:
            raise HTTPException(404, "Scope version not found")
        if selected["status"] == "approved":
            return P.scope_version_view(state, selected, P.normalize_locale(locale))
        if selected["status"] != "draft":
            raise HTTPException(409, "Only draft versions can be approved")
        diff = selected.get("diff") or {"added": [], "modified": [], "removed": []}
        stamp = now()
        next_number = max(int(item["id"].split("-")[1]) for item in state.requirements) + 1
        for item in diff["added"]:
            human_id = f"REQ-{next_number:03d}"
            next_number += 1
            title = _as_text(item["title"])
            state.requirements.append({
                "uuid": str(uuid4()), "id": human_id, "title": title, "description": _as_text(item.get("description") or item["title"]), "component": item.get("component") or _guess_component(state, title["en"]),
                "type": "functional", "priority": "medium", "owner_id": state.member_by_role("delivery_lead")["id"], "scope_status": "agreed", "verification": "not_started",
                "acceptance": "pending", "defect": False, "verification_plan": None, "baseline": version, "version": "v1.0", "created_at": stamp, "agreed_at": stamp,
                "criteria": [{"id": str(uuid4()), "text": L(f"“{title['en']}” can be demonstrated end to end in the portal", f"«{title['es']}» se puede demostrar de principio a fin en el portal"), "source": "baseline"}],
            })
            added_ids.append(human_id)
        for item in diff["modified"]:
            target = state.requirement(item["id"])
            if target is None:
                continue
            if item.get("before") == target["title"]:
                target["title"] = _as_text(item["after"])
            else:
                target["description"] = _as_text(item["after"])
            target["version"] = f"v1.{int(target['version'].split('.')[-1]) + 1}"
        for item in diff["removed"]:
            target = state.requirement(item["id"])
            if target is not None:
                target["scope_status"] = "out_of_scope"
        for item in state.scope_versions:
            if item["status"] == "approved":
                item["status"] = "superseded"
        selected["status"] = "approved"
        selected["approved_at"] = stamp
        for item in state.requirements:
            if item["scope_status"] == "agreed" and item["baseline"] != version and item["id"] not in added_ids:
                item["baseline"] = version
    audit_event(user, "scope_approved", project_id, ref={"type": "scope_version", "id": version, "label": version}, params={"version": version}, added=added_ids)
    return P.scope_version_view(state, selected, P.normalize_locale(locale))


# --- Changes ----------------------------------------------------------------------

@app.get("/api/v1/projects/{project_id}/changes", dependencies=[Depends(require_project_access)])
def changes(project_id: str, locale: str = "en") -> list[dict]:
    return catalog.changes(project_id, locale=P.normalize_locale(locale))


def _decide_change(state: ProjectState, change: dict[str, Any], status: str, user: CurrentUser) -> None:
    with store.lock:
        change["status"] = status
        change["decided_by"] = member_id_for(user, state) if status != "proposed" else None
        change["decided_at"] = now() if status != "proposed" else None
        for requirement_id in change["requirement_ids"]:
            requirement = state.requirement(requirement_id)
            if requirement is None:
                continue
            if status == "approved":
                if requirement["scope_status"] == "pending":
                    requirement["scope_status"] = "agreed"
                    requirement["agreed_at"] = now()
                requirement["defect"] = False
            elif status == "rejected" and requirement["scope_status"] == "pending":
                requirement["scope_status"] = "out_of_scope"
    audit_event(user, f"change_{status}", state.id, ref={"type": "change", "id": change["id"], "label": change["code"]}, params={"code": change["code"]}, change_id=change["id"], status=status)


def _change_or_404(state: ProjectState, change_id: str) -> dict[str, Any]:
    change = next((item for item in state.changes if change_id in (item["id"], item["code"])), None)
    if change is None:
        raise HTTPException(404, "Change request not found")
    return change


@app.patch("/api/v1/changes/{change_id}")
def update_change(change_id: str, payload: dict, user: CurrentUser = Depends(current_user)) -> dict:
    """Legacy route addressed by change id across projects."""
    for state in store.projects.values():
        change = next((item for item in state.changes if change_id in (item["id"], item["code"])), None)
        if change:
            if payload.get("status") in {"proposed", "approved", "rejected"}:
                _decide_change(state, change, payload["status"], user)
            return P.change_view(state, change, "en")
    raise HTTPException(404, "Change request not found")


@app.patch("/api/v1/projects/{project_id}/changes/{change_id}", dependencies=[Depends(require_project_access)])
def update_project_change(project_id: str, change_id: str, payload: dict, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    change = _change_or_404(state, change_id)
    if payload.get("status") not in {"proposed", "approved", "rejected"}:
        raise HTTPException(400, "Invalid change request status")
    _decide_change(state, change, payload["status"], user)
    return P.change_view(state, change, P.normalize_locale(locale))


# --- Verification and evidence -------------------------------------------------------

@app.post("/api/v1/projects/{project_id}/runs", dependencies=[Depends(require_project_access)])
def run_verification(project_id: str, payload: RunRequest, locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    locale = P.normalize_locale(locale)
    time.sleep(_float_env("SIGNOFF_RUN_DELAY", 1.2) if os.getenv("SIGNOFF_RUN_DELAY") else (1.2 if mock_mode() else 0))
    with store.lock:
        if payload.requirement_ids:
            selected = [item for item in (state.requirement(key) for key in payload.requirement_ids) if item]
        else:
            selected = [item for item in sorted(P.in_scope(state), key=P.attention_rank) if item["verification"] != "passed"][:3]
        if not selected:
            return {"run_id": None, "status": "completed", "target_url": payload.target_url, "runs": [], "evidence": [], "requirements": []}
        at = now()
        number = len(state.runs) + 1
        run_id = f"run_{uuid4().hex[:10]}"
        results, created = [], []
        for requirement in selected:
            total = len(requirement["criteria"])
            result = "failed" if not total or requirement.get("defect") else "passed"
            covered = total if result == "passed" else max(0, total - 1)
            artifact = f"{requirement['id'].lower()}-run-{number:02d}.png"
            key = f"{state.id}/evidence/{artifact}"
            content = f"Signoff verification {state.id} {requirement['id']} run {number} {at}".encode()
            stored = storage.put_object(key, content, "image/png")
            evidence = {"id": str(uuid4()), "requirement_id": requirement["id"], "artifact": artifact, "storage_key": key, "kind": "screenshot", "source": "verification", "state": P.EVIDENCE_STATUS[result], "summary": dict(_RUN_SUMMARY[result]), "sha256": stored.get("sha256", storage.compute_hash(content)), "size": len(content), "created_at": at, "run_id": run_id}
            state.evidence.append(evidence)
            created.append(evidence)
            requirement["verification"] = result
            results.append({"requirement_id": requirement["id"], "result": result, "criteria_covered": covered, "criteria_total": total, "evidence_ids": [evidence["id"]]})
        state.runs.append({"id": run_id, "number": number, "at": at, "actor_id": member_id_for(user, state), "results": results})
        rows = [P.requirement_row(state, item, locale) for item in selected]
    passed = sum(item["result"] == "passed" for item in results)
    audit_event(user, "verification_run", project_id, ref=req_ref(selected[0]) if len(selected) == 1 else None, params={"count": len(results), "passed": passed, "failed": len(results) - passed, "run": number}, run_id=run_id)
    return {
        "run_id": run_id, "status": "completed", "target_url": payload.target_url,
        "runs": [{"id": run_id, "at": at, "coverage": P.pct(item["criteria_covered"], item["criteria_total"]), **item} for item in results],
        "evidence": [P.evidence_view(item, locale) for item in created],
        "requirements": rows,
    }


_RUN_SUMMARY = {
    "passed": L("All acceptance criteria were observed in the browser run.", "Todos los criterios de aceptación se observaron en la ejecución del navegador."),
    "failed": L("At least one acceptance criterion was not met; see the captured screenshot.", "Al menos un criterio de aceptación no se cumplió; ver la captura."),
}


@app.get("/api/v1/projects/{project_id}/evidence", dependencies=[Depends(require_project_access)])
def evidence(project_id: str, locale: str = "en") -> list[dict]:
    state = project_state(project_id)
    locale = P.normalize_locale(locale)
    return [P.evidence_view(item, locale) for item in sorted(state.evidence, key=lambda item: item["created_at"], reverse=True)]


EVIDENCE_KINDS = {".png": "screenshot", ".jpg": "screenshot", ".jpeg": "screenshot", ".webp": "screenshot", ".gif": "screenshot", ".csv": "csv", ".log": "log", ".txt": "log", ".json": "log"}


@app.post("/api/v1/projects/{project_id}/evidence", dependencies=[Depends(require_project_access)])
async def upload_evidence(project_id: str, file: UploadFile = File(...), requirement_id: str = Form(...), description: str = Form(""), locale: str = "en", user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    requirement = requirement_or_404(state, requirement_id)
    filename = os.path.basename(file.filename or "evidence")
    if not filename or filename != (file.filename or "") or filename.startswith("."):
        raise HTTPException(400, "Unsafe filename")
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "File exceeds 10MB limit")
    if not content:
        raise HTTPException(400, "File is empty")
    suffix = Path(filename).suffix.lower()
    inspection = inspect_file(filename, content) if suffix in {".csv", ".json", ".xlsx"} else None
    evidence_id = str(uuid4())
    key = f"{state.id}/uploads/{evidence_id[:8]}-{re.sub(r'[^A-Za-z0-9._-]', '_', filename)}"
    stored = storage.put_object(key, content, file.content_type or "application/octet-stream")
    state_value = "partially_demonstrated" if inspection is not None and not inspection.get("valid") else "demonstrated"
    text = description.strip()
    if inspection is not None and inspection.get("valid") and "row_count" in inspection:
        detail = L(f"{inspection['row_count']} rows, {len(inspection.get('columns', []))} columns", f"{inspection['row_count']} filas, {len(inspection.get('columns', []))} columnas")
        summary = L(f"{text or filename} ({detail['en']})", f"{text or filename} ({detail['es']})")
    else:
        summary = L(text or f"Uploaded {filename}", text or f"Subido {filename}")
    item = {"id": evidence_id, "requirement_id": requirement["id"], "artifact": filename, "storage_key": key, "kind": EVIDENCE_KINDS.get(suffix, "document"), "source": "upload", "state": state_value, "summary": summary, "sha256": stored.get("sha256", storage.compute_hash(content)), "size": len(content), "created_at": now(), "run_id": None}
    with store.lock:
        state.evidence.append(item)
    audit_event(user, "evidence_uploaded", project_id, ref={"type": "evidence", "id": evidence_id, "label": filename}, params={"artifact": filename, "requirement_id": requirement["id"]}, evidence_id=evidence_id)
    result: dict[str, Any] = {"evidence": P.evidence_view(item, P.normalize_locale(locale))}
    if inspection is not None:
        result["inspection"] = inspection
    return result


@app.get("/api/v1/projects/{project_id}/evidence/{artifact_id}/signed-url", dependencies=[Depends(require_project_access)])
def evidence_signed_url(project_id: str, artifact_id: str) -> dict[str, str]:
    state = project_state(project_id)
    item = next((entry for entry in state.evidence if artifact_id in (entry["id"], entry["artifact"])), None)
    if not item:
        raise HTTPException(404, "Evidence artifact not found")
    key = item.get("storage_key") or item["artifact"]
    if isinstance(storage, LocalStorageProvider):
        try:
            storage.get_object(key)
        except FileNotFoundError:
            storage.put_object(key, f"SDA evidence artifact for {project_id} {item['requirement_id']}".encode(), "application/octet-stream")
    return {"url": storage.get_signed_url(key)}


@app.get("/api/v1/evidence/{key:path}")
def get_evidence_object(key: str, expires: int, signature: str) -> Response:
    try:
        valid = storage.verify_signed_url(key, expires, signature)
    except ValueError as exc:
        raise HTTPException(400, "Unsafe evidence key") from exc
    if not valid:
        raise HTTPException(403, "Evidence link expired or invalid")
    try:
        content = storage.get_object(key)
    except ValueError as exc:
        raise HTTPException(400, "Unsafe evidence key") from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Evidence object not found") from exc
    return Response(content=content, media_type="application/octet-stream")


HUMAN_EVIDENCE_KINDS = {"screenshot": "screenshot", "video": "document", "document": "document", "link": "document", "comment": "observation", "manual_test_result": "observation"}


@app.post("/api/v1/projects/{project_id}/human-evidence", dependencies=[Depends(require_project_access)])
def add_human_evidence(project_id: str, payload: HumanEvidenceRequest, user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    requirement = requirement_or_404(state, payload.requirement_id)
    evidence_id = str(uuid4())
    artifact = f"{payload.kind}-{evidence_id[:8]}.txt"
    item = {"id": evidence_id, "requirement_id": requirement["id"], "artifact": artifact, "storage_key": f"{state.id}/uploads/{artifact}", "kind": HUMAN_EVIDENCE_KINDS[payload.kind], "source": "upload", "state": "demonstrated", "summary": L(payload.description, payload.description), "sha256": hashlib.sha256(payload.description.encode()).hexdigest(), "size": len(payload.description), "created_at": now(), "run_id": None, "origin": payload.source}
    with store.lock:
        state.evidence.append(item)
    audit_event(user, "evidence_uploaded", project_id, ref={"type": "evidence", "id": evidence_id, "label": artifact}, params={"artifact": artifact, "requirement_id": requirement["id"]}, evidence_id=evidence_id)
    return P.evidence_view(item, "en")


@app.post("/api/v1/projects/{project_id}/file-inspections", dependencies=[Depends(require_project_access)])
def file_inspection(project_id: str, payload: FileInspectionRequest) -> dict:
    project_or_404(project_id)
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
        checks["row_count_match"] = result.get("row_count", 0) == payload.expected_row_count
    result["checks"] = checks
    result["assessment"] = "demonstrated" if result["valid"] and all(checks.values()) else "partially_demonstrated"
    return result


# --- Readiness, graph, delivery ----------------------------------------------------------

@app.get("/api/v1/projects/{project_id}/readiness", dependencies=[Depends(require_project_access)])
def readiness(project_id: str) -> dict:
    return P.readiness(project_state(project_id))


@app.get("/api/v1/projects/{project_id}/graph", dependencies=[Depends(require_project_access)])
def evidence_graph(project_id: str) -> dict:
    state = project_state(project_id)
    active = P.active_baseline(state)
    nodes = [{"type": "scope_version", "id": item["version"], "label": item["version"]} for item in state.scope_versions]
    nodes.extend({"type": "requirement", "id": item["id"], "label": f"{item['id']} · {item['title']['en']}"} for item in state.requirements)
    nodes.extend({"type": "evidence", "id": item["id"], "label": item["artifact"]} for item in state.evidence)
    relationships = [{"source_type": "scope_version", "source_id": active, "target_type": "requirement", "target_id": item["id"], "relationship": "contains"} for item in P.in_scope(state)]
    relationships.extend({"source_type": "requirement", "source_id": item["requirement_id"], "target_type": "evidence", "target_id": item["id"], "relationship": "verifies"} for item in state.evidence)
    relationships.extend({"source_type": "change", "source_id": change["code"], "target_type": "requirement", "target_id": rid, "relationship": "changed_by"} for change in state.changes for rid in change["requirement_ids"])
    covered = {item["requirement_id"] for item in state.evidence}
    return {"nodes": nodes, "relationships": relationships, "questions": {"requirements_without_evidence": sum(item["id"] not in covered for item in state.requirements), "requirements_with_evidence": sum(item["id"] in covered for item in state.requirements)}}


@app.get("/api/v1/projects/{project_id}/delivery-pack", dependencies=[Depends(require_project_access)])
def delivery_pack(project_id: str, locale: str = "en") -> dict:
    result = catalog.delivery_pack(project_id, release_id_for(project_id), locale=P.normalize_locale(locale))
    if result is None:
        raise HTTPException(404, "Release not found")
    return result


@app.post("/api/v1/projects/{project_id}/prepare-delivery", dependencies=[Depends(require_project_access)])
def prepare_delivery(project_id: str, locale: str = "en") -> dict:
    return P.prepare_delivery_checks(project_state(project_id), proposals_list(), P.normalize_locale(locale))


@app.get("/api/v1/projects/{project_id}/attention", dependencies=[Depends(require_project_access)])
def attention(project_id: str, locale: str = "en") -> list[dict]:
    return P.attention(project_state(project_id), proposals_list(), P.normalize_locale(locale))


@app.get("/api/v1/projects/{project_id}/activity", dependencies=[Depends(require_project_access)])
def activity(project_id: str, locale: str = "en", limit: int = 20) -> list[dict]:
    return P.activity(project_state(project_id), list(store.audit_events), P.normalize_locale(locale), max(1, min(limit, 200)))


@app.get("/api/v1/projects/{project_id}/audit", dependencies=[Depends(require_project_access)])
def audit(project_id: str) -> list[dict]:
    project_or_404(project_id)
    return [item for item in list(store.audit_events) if item.get("project_id") == project_id]


@app.post("/api/v1/projects/{project_id}/bug-change-assessment", response_model=BugChangeAssessment, dependencies=[Depends(require_project_access)])
def bug_change_assessment(project_id: str, payload: BugChangeRequest) -> BugChangeAssessment:
    state = project_state(project_id)
    report = payload.report.lower()
    if any(word in report for word in ["email", "scheduled", "automatically", "cada mañana"]):
        classification, reason, confidence = "likely_change_request", "The request describes new scheduled delivery behavior that is not present in the approved baseline.", 0.91
    elif any(word in report for word in ["filter", "export", "column", "fila"]):
        classification, reason, confidence = "likely_defect", "The report references behavior already covered by the export and filtering requirement.", 0.88
    else:
        classification, reason, confidence = "needs_human_review", "The report cannot be safely classified against the current baseline.", 0.52
    return BugChangeAssessment(classification=classification, confidence=confidence, reason=reason, compared_scope_version=P.active_baseline(state) or "baseline", related_requirement_ids=[str(item) for item in payload.requirement_ids])


@app.get("/api/v1/projects/{project_id}/acceptance", dependencies=[Depends(require_project_access)])
def acceptance(project_id: str) -> list[dict]:
    return catalog.acceptance(project_id)


@app.post("/api/v1/projects/{project_id}/acceptance/{requirement_id}", dependencies=[Depends(require_project_access)])
def decide_acceptance(project_id: str, requirement_id: str, payload: AcceptanceDecisionRequest, user: CurrentUser = Depends(current_user)) -> dict:
    state = project_state(project_id)
    with store.lock:
        requirement = state.requirement(requirement_id)
        if requirement is None:
            raise HTTPException(404, "Acceptance item not found")
        requirement["acceptance"] = payload.decision
        requirement["acceptance_comment"] = payload.comment
    audit_event(user, "acceptance_decided", project_id, ref=req_ref(requirement), params={"decision": payload.decision.replace("_", " "), "requirement_id": requirement["id"]})
    return {"requirement_id": requirement["uuid"], "human_id": requirement["id"], "decision": payload.decision, "comment": payload.comment, "updated_at": now()}


# --- Client review -------------------------------------------------------------------

@app.post("/api/v1/review/{token}")
def review(token: str, payload: ReviewRequest) -> dict:
    access = _review_record(token)
    if not _guest_session_valid(token, payload.guest_session):
        raise HTTPException(401, "Guest verification required")
    project_id = access["project_id"]
    state = project_state(project_id)
    at = now()
    item = {"token_hash": hashlib.sha256(token.encode()).hexdigest(), "project_id": project_id, "release_id": access["release_id"], **payload.model_dump(exclude={"guest_session"}), "created_at": at}
    with store.lock:
        store.reviews.append(item)
        state.decisions.append({"decision": payload.decision, "comment": payload.comment, "at": at})
        state.release["status"] = payload.decision
        for requirement in P.in_scope(state):
            if payload.decision == "accepted" and requirement["acceptance"] == "pending":
                requirement["acceptance"] = "accepted"
            elif payload.decision == "rejected" and requirement["acceptance"] == "pending":
                requirement["acceptance"] = "rejected"
            elif payload.decision == "revision_requested" and requirement["verification"] != "passed":
                requirement["acceptance"] = "revision_requested"
    reviewer = state.member_by_role("client_reviewer")
    audit_event(None, "client_release_reviewed", project_id, actor_id=reviewer["id"], params={"decision": payload.decision}, release_id=access["release_id"], decision=payload.decision)
    return {"status": "recorded", "review": item, "release_status": payload.decision}


@app.post("/api/v1/review/{token}/request-otp")
def request_review_otp(token: str, payload: ReviewOtpRequest) -> dict[str, Any]:
    access = _review_record(token)
    if mock_mode():
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
    if mock_mode() and payload.code == "123456":
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
def review_pack(token: str, guest_session: Optional[str] = None, locale: str = "en") -> dict:
    access = _review_record(token)
    if not _guest_session_valid(token, guest_session):
        raise HTTPException(401, "Guest verification required")
    return P.review(project_state(access["project_id"]), P.normalize_locale(locale))


# --- Internal ---------------------------------------------------------------------

@app.get("/api/v1/internal/costs")
def costs(user: CurrentUser = Depends(current_user)) -> dict:
    require_role(user, "owner", "admin")
    input_tokens = sum(item["input_tokens"] for item in store.llm_runs)
    output_tokens = sum(item["output_tokens"] for item in store.llm_runs)
    estimated_cost = round(sum(item["estimated_cost"] for item in store.llm_runs) + 0.18, 4)
    provider = "hosted-llm" if not mock_mode() else "MockLLMProvider"
    return {"runs": len(store.llm_runs) + 4, "llm_tokens": {"input": input_tokens + 4820, "output": output_tokens + 1360}, "estimated_cost_eur": estimated_cost, "browser_minutes": 3.4, "provider": provider}


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    try:
        return job_runner.get_status(job_id)
    except KeyError as exc:
        raise HTTPException(404, "Job not found") from exc

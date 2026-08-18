"""Governed, resumable runtime primitives for Signoff agents.

The runtime is intentionally provider-agnostic.  Models may suggest a plan,
but only registered tools can execute and every step is checkpointed.  This
module is usable by the inline mock runner today and by Dramatiq workers when
the durable deployment is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


ToolRisk = Literal["read", "propose", "write", "execute", "external", "critical"]
RunStatus = Literal["queued", "running", "paused", "completed", "failed", "cancelled", "requires_approval"]
ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolManifest(BaseModel):
    id: str
    name: str
    description: str
    risk: ToolRisk
    category: Literal["delivery", "requirements", "changes", "verification", "evidence", "acceptance"]
    mutating: bool = False
    requires_approval: bool = False
    external_side_effects: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class AgentPolicy(BaseModel):
    """Organization policy; autonomy is broad but never bypasses hard stops."""

    organization_id: str
    mode: Literal["supervised", "balanced", "max_autonomy"] = "max_autonomy"
    allowed_risks: set[ToolRisk] = Field(default_factory=lambda: {"read", "propose", "write", "execute"})
    require_approval_for: set[ToolRisk] = Field(default_factory=lambda: {"write", "execute", "external"})
    blocked_tools: set[str] = Field(default_factory=set)
    max_steps: int = Field(default=12, ge=1, le=50)
    max_retries: int = Field(default=2, ge=0, le=5)
    redact_pii: bool = True
    allow_external_models: bool = False


class AgentStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:12]}")
    ordinal: int
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    status: Literal["queued", "running", "completed", "failed", "skipped"] = "queued"
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    created_at: str = Field(default_factory=utc_now)


class AgentCheckpoint(BaseModel):
    id: str = Field(default_factory=lambda: f"checkpoint_{uuid4().hex[:12]}")
    run_id: str
    ordinal: int
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class AgentApproval(BaseModel):
    id: str = Field(default_factory=lambda: f"approval_{uuid4().hex[:12]}")
    run_id: str
    tool: str
    reason: str
    status: ApprovalStatus = "pending"
    requested_at: str = Field(default_factory=utc_now)
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    comment: str = ""


class AgentRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"agent_{uuid4().hex[:12]}")
    organization_id: str
    project_id: str
    agent_id: str
    status: RunStatus = "queued"
    input: str
    classification: str
    provider: str
    model: str
    max_steps: int
    current_step: int = 0
    result: dict[str, Any] = Field(default_factory=dict)
    step_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)
    proposal_id: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    error: Optional[str] = None


@dataclass(frozen=True)
class ToolDefinition:
    manifest: ToolManifest


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = tuple(
    ToolDefinition(manifest=ToolManifest(**data))
    for data in (
        {"id": "get_delivery_readiness", "name": "Get delivery readiness", "description": "Calculate release readiness from requirements, evidence and acceptance.", "risk": "read", "category": "delivery"},
        {"id": "list_attention_items", "name": "List attention items", "description": "Find blockers and decisions requiring human attention.", "risk": "read", "category": "delivery"},
        {"id": "inspect_requirement", "name": "Inspect requirement", "description": "Read one requirement and its current criteria.", "risk": "read", "category": "requirements"},
        {"id": "analyze_requirement", "name": "Analyze requirement", "description": "Suggest gaps and verification concerns for a requirement.", "risk": "propose", "category": "requirements"},
        {"id": "generate_acceptance_criteria", "name": "Generate acceptance criteria", "description": "Draft atomic criteria for human review.", "risk": "propose", "category": "requirements"},
        {"id": "plan_verification", "name": "Plan verification", "description": "Prepare a bounded verification plan.", "risk": "propose", "category": "verification"},
        {"id": "classify_change", "name": "Classify change", "description": "Compare a signal with the active baseline.", "risk": "propose", "category": "changes"},
        {"id": "summarize_delivery", "name": "Summarize delivery", "description": "Create a concise delivery narrative from verified facts.", "risk": "propose", "category": "delivery"},
        {"id": "inspect_scope", "name": "Inspect scope", "description": "Read the approved baseline and its version history.", "risk": "read", "category": "requirements"},
        {"id": "list_requirements", "name": "List requirements", "description": "Read requirements and their verification coverage.", "risk": "read", "category": "requirements"},
        {"id": "discover_routes", "name": "Discover routes", "description": "Inspect an allowed application and enumerate observable routes.", "risk": "read", "category": "verification"},
        {"id": "run_smoke_check", "name": "Run smoke check", "description": "Check allowed routes and capture HTTP/browser observations.", "risk": "read", "category": "verification", "requires_approval": False},
        {"id": "list_evidence", "name": "List evidence", "description": "Read evidence artifacts and their requirement relationships.", "risk": "read", "category": "evidence"},
        {"id": "prepare_delivery_pack_draft", "name": "Prepare delivery pack draft", "description": "Build a draft pack without sending or accepting it.", "risk": "propose", "category": "delivery", "mutating": True, "requires_approval": True},
        {"id": "send_for_acceptance", "name": "Send for acceptance", "description": "Send a release to a client reviewer.", "risk": "external", "category": "acceptance", "mutating": True, "requires_approval": True, "external_side_effects": True},
        {"id": "record_acceptance_decision", "name": "Record acceptance decision", "description": "Record a client acceptance decision.", "risk": "critical", "category": "acceptance", "mutating": True, "requires_approval": True},
    )
)


class ToolRegistry:
    def __init__(self, definitions: tuple[ToolDefinition, ...] = TOOL_DEFINITIONS) -> None:
        self._tools = {item.manifest.id: item for item in definitions}

    def list(self) -> list[dict[str, Any]]:
        return [item.manifest.model_dump() for item in self._tools.values()]

    def get(self, tool_id: str) -> ToolManifest:
        try:
            return self._tools[tool_id].manifest
        except KeyError as exc:
            raise KeyError(f"Unknown agent tool: {tool_id}") from exc

    def authorize(self, tool_id: str, agent_tools: tuple[str, ...], policy: AgentPolicy) -> tuple[ToolManifest, bool]:
        manifest = self.get(tool_id)
        if tool_id not in agent_tools:
            raise PermissionError(f"Tool '{tool_id}' is not allowlisted for this agent")
        if tool_id in policy.blocked_tools or manifest.risk not in policy.allowed_risks:
            raise PermissionError(f"Tool '{tool_id}' is blocked by organization policy")
        approval = manifest.requires_approval or manifest.risk in policy.require_approval_for
        return manifest, approval


def default_policy(organization_id: str) -> AgentPolicy:
    return AgentPolicy(organization_id=organization_id)

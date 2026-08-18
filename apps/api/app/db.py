"""Production persistence blueprint.

The demo continues to use the in-memory repository. These SQLAlchemy models
define the durable shape used by the PostgreSQL migration increment.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Organization(Timestamped, Base):
    __tablename__ = "organizations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class Project(Timestamped, Base):
    __tablename__ = "projects"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    client: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    organization: Mapped[Organization] = relationship(back_populates="projects")


class ScopeVersion(Timestamped, Base):
    __tablename__ = "scope_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_scope_project_version"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    source: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(160), default="system")


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="")


class Membership(Timestamped, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="member")


class Client(Timestamped, Base):
    __tablename__ = "clients"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)


class ScopeDocument(Timestamped, Base):
    __tablename__ = "scope_documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(160))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default="uploaded")


class RequirementSource(Timestamped, Base):
    __tablename__ = "requirement_sources"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("requirements.id"), index=True)
    document_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scope_documents.id"), nullable=True)
    page: Mapped[Optional[int]] = mapped_column(nullable=True)
    section: Mapped[str] = mapped_column(String(240), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(default=0)


class Requirement(Timestamped, Base):
    __tablename__ = "requirements"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    scope_version_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scope_versions.id"), nullable=True)
    human_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), default="manual_review_required")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AcceptanceCriterion(Timestamped, Base):
    __tablename__ = "acceptance_criteria"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("requirements.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    evaluation_type: Mapped[str] = mapped_column(String(32), default="semantic")
    automated: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class ChangeRequest(Timestamped, Base):
    __tablename__ = "change_requests"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ChangeEvidence(Timestamped, Base):
    __tablename__ = "change_evidence"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    change_request_id: Mapped[UUID] = mapped_column(ForeignKey("change_requests.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_ref: Mapped[str] = mapped_column(String(500))
    excerpt: Mapped[str] = mapped_column(Text, default="")


class VerificationRun(Timestamped, Base):
    __tablename__ = "verification_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    target_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class VerificationStep(Timestamped, Base):
    __tablename__ = "verification_steps"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("verification_runs.id"), index=True)
    ordinal: Mapped[int] = mapped_column(default=0)
    action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    observation_json: Mapped[dict] = mapped_column(JSON, default=dict)


class VerificationResult(Timestamped, Base):
    __tablename__ = "verification_results"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("verification_runs.id"), index=True)
    criterion_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("acceptance_criteria.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(48))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    observation_refs: Mapped[list] = mapped_column(JSON, default=list)


class EvidenceArtifact(Timestamped, Base):
    __tablename__ = "evidence_artifacts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    verification_run_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("verification_runs.id"), nullable=True)
    requirement_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(160))
    sha256: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceRelationship(Timestamped, Base):
    __tablename__ = "evidence_relationships"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_id: Mapped[str] = mapped_column(String(160))
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(160))
    relationship: Mapped[str] = mapped_column(String(80))


class DeliveryPack(Timestamped, Base):
    __tablename__ = "delivery_packs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    release_id: Mapped[UUID] = mapped_column(ForeignKey("delivery_releases.id"), index=True)
    format: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Comment(Timestamped, Base):
    __tablename__ = "comments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    author_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class IntegrationConnection(Timestamped, Base):
    __tablename__ = "integration_connections"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeliveryRelease(Timestamped, Base):
    __tablename__ = "delivery_releases"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    scope_version_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("scope_versions.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AcceptanceDecision(Timestamped, Base):
    __tablename__ = "acceptance_decisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    release_id: Mapped[UUID] = mapped_column(ForeignKey("delivery_releases.id"), index=True)
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("requirements.id"), index=True)
    actor_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    decision: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Timestamped, Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class LLMRun(Timestamped, Base):
    __tablename__ = "llm_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    estimated_cost: Mapped[float] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(32), default="completed")


class AIConsent(Timestamped, Base):
    __tablename__ = "ai_consents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(240), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model_or_route: Mapped[str] = mapped_column(String(160))
    classification: Mapped[str] = mapped_column(String(40), default="CONFIDENTIAL")
    purpose: Mapped[str] = mapped_column(Text)
    granted_by: Mapped[str] = mapped_column(String(160))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentPolicy(Timestamped, Base):
    __tablename__ = "agent_policies"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), default="max_autonomy")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(Timestamped, Base):
    __tablename__ = "agent_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    classification: Mapped[str] = mapped_column(String(40), default="CONFIDENTIAL")
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    current_step: Mapped[int] = mapped_column(default=0)
    max_steps: Mapped[int] = mapped_column(default=12)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AgentStep(Timestamped, Base):
    __tablename__ = "agent_steps"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    ordinal: Mapped[int] = mapped_column(default=0)
    tool: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)


class AgentCheckpoint(Timestamped, Base):
    __tablename__ = "agent_checkpoints"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    ordinal: Mapped[int] = mapped_column(default=0)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentApproval(Timestamped, Base):
    __tablename__ = "agent_approvals"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    decided_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")

"""PostgreSQL adapter used when production persistence is enabled.

The adapter owns no business rules. It stores the canonical project/release
projection and the normalized entities that support it, while the service
layer remains the only place that decides what a mutation means.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .catalog import ProjectCatalog
from .db import AcceptanceCriterion, AIConsent, AgentApproval as DbAgentApproval, AgentCheckpoint as DbAgentCheckpoint, AgentPolicy as DbAgentPolicy, AgentRun as DbAgentRun, AgentStep as DbAgentStep, Base, DeliveryRelease, Organization, Project, Requirement, ScopeVersion, User, Membership


def stable_uuid(value: str):
    return uuid5(NAMESPACE_URL, f"https://sda.local/{value}")


class PostgresRepository:
    """Tenant-aware SQLAlchemy repository for the canonical demo workspace."""

    def __init__(self, database_url: str | None = None) -> None:
        raw_url = database_url or os.getenv("DATABASE_URL", "postgresql+asyncpg://sda:sda@localhost:5432/sda")
        self.database_url = raw_url.replace("+asyncpg", "+psycopg")
        self.engine = create_engine(self.database_url, pool_pre_ping=True, future=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self, catalog: ProjectCatalog) -> None:
        Base.metadata.create_all(self.engine)
        with self.session_factory.begin() as session:
            organization = session.scalar(select(Organization).where(Organization.id == stable_uuid("org_demo")))
            if organization is None:
                organization = Organization(id=stable_uuid("org_demo"), name="Signoff Demo Organization")
                session.add(organization)
            owner = session.scalar(select(User).where(User.id == stable_uuid("demo-owner")))
            if owner is None:
                owner = User(id=stable_uuid("demo-owner"), email="owner@demo.sda", display_name="Demo owner")
                session.add(owner)
                session.add(Membership(id=stable_uuid("membership-demo-owner"), organization_id=organization.id, user_id=owner.id, role="owner"))
            for item in catalog.list_projects():
                project = session.scalar(select(Project).where(Project.slug == item["slug"]))
                if project is None:
                    project = Project(id=stable_uuid(item["id"]), organization_id=organization.id, name=item["name"], slug=item["slug"], client=item["client"], description=item["description"], metadata_json={})
                    session.add(project)
                release = session.scalar(select(DeliveryRelease).where(DeliveryRelease.id == stable_uuid(item["release_id"])))
                if release is None:
                    release_data = catalog.list_releases(item["id"])[0]
                    release = DeliveryRelease(id=stable_uuid(item["release_id"]), project_id=project.id, name=release_data["name"], version=release_data["version"], status=release_data["status"], scope_version_id=None, metadata_json={"slug": item["release_id"], "target_date": release_data["target_date"]})
                    session.add(release)
                projection = catalog.dashboard(item["id"], item["release_id"])
                project.metadata_json = {
                    "dashboard": projection,
                    "canonical_id": item["id"],
                    "release_id": item["release_id"],
                    "organization_id": item["organization_id"],
                    "requirements_count": item["requirements_count"],
                    "requirements": catalog.requirements(item["id"]),
                    "changes": catalog.changes(item["id"]),
                    "scope_versions": catalog.scope_versions(item["id"]),
                    "attention": catalog.attention(item["id"]),
                    "acceptance": catalog.acceptance(item["id"]),
                    "delivery_pack": catalog.delivery_pack(item["id"], item["release_id"]),
                }
                session.add(project)
                self._seed_requirements(session, project.id, item["id"], projection or {})

    def _seed_requirements(self, session: Session, project_id: Any, project_key: str, projection: dict[str, Any]) -> None:
        rows = projection.get("requirements", [])
        for row in rows:
            requirement_id = stable_uuid(f"{project_key}:{row['id']}")
            requirement = session.scalar(select(Requirement).where(Requirement.id == requirement_id))
            if requirement is None:
                requirement = Requirement(id=requirement_id, project_id=project_id, human_id=row["id"], title=row["title"], description=row["title"], status=row.get("status", "pending"), metadata_json=row)
                session.add(requirement)
            detail = projection.get("selected_requirement") if row["id"] == projection.get("selected_requirement", {}).get("id") else None
            for index, criterion_text in enumerate((detail or {}).get("criteria", []), 1):
                criterion_id = stable_uuid(f"{project_key}:{row['id']}:criterion:{index}")
                if session.scalar(select(AcceptanceCriterion).where(AcceptanceCriterion.id == criterion_id)) is None:
                    session.add(AcceptanceCriterion(id=criterion_id, requirement_id=requirement_id, text=criterion_text, evaluation_type="semantic", automated=True, status="approved"))

    def _project_query(self, session: Session, organization_id: str | None = None) -> list[Project]:
        statement = select(Project).where(Project.organization_id == stable_uuid(organization_id or "org_demo"))
        return list(session.scalars(statement))

    def _find_project(self, session: Session, project_id: str, organization_id: str) -> Project | None:
        return next((item for item in self._project_query(session, organization_id) if item.slug == project_id or (item.metadata_json or {}).get("canonical_id") == project_id), None)

    def list_projects(self, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return [self._project_dict(project) for project in self._project_query(session, organization_id)]

    def membership_role(self, user_id: str, organization_id: str) -> str | None:
        """Return the role only when the user belongs to the requested tenant."""
        with self.session_factory() as session:
            membership = session.scalar(
                select(Membership)
                .join(User, Membership.user_id == User.id)
                .where(
                    Membership.user_id == stable_uuid(user_id),
                    Membership.organization_id == stable_uuid(organization_id),
                )
            )
            return membership.role if membership else None

    def list_ai_consents(self, project_id: str, organization_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            project = self._find_project(session, project_id, organization_id)
            if project is None:
                return []
            rows = session.scalars(select(AIConsent).where(AIConsent.project_id == project.id, AIConsent.organization_id == stable_uuid(organization_id), AIConsent.revoked_at.is_(None)))
            return [{"id": str(row.id), "organization_id": organization_id, "project_id": project_id, "document_id": row.document_id, "provider": row.provider, "model_or_route": row.model_or_route, "classification": row.classification, "purpose": row.purpose, "granted_by": row.granted_by, "granted_at": row.granted_at.isoformat() if row.granted_at else None, "expires_at": row.expires_at.isoformat(), "revoked_at": None} for row in rows]

    def save_ai_consent(self, record: dict[str, Any]) -> None:
        from datetime import datetime
        with self.session_factory.begin() as session:
            project = self._find_project(session, record["project_id"], record["organization_id"])
            if project is None:
                return
            consent = AIConsent(id=stable_uuid(record["id"]), organization_id=stable_uuid(record["organization_id"]), project_id=project.id, document_id=record["document_id"], provider=record["provider"], model_or_route=record["model_or_route"], classification=record["classification"], purpose=record["purpose"], granted_by=record["granted_by"], expires_at=datetime.fromisoformat(record["expires_at"]))
            session.merge(consent)

    def revoke_ai_consent(self, project_id: str, document_id: str, organization_id: str) -> int:
        from datetime import datetime, timezone
        with self.session_factory.begin() as session:
            project = self._find_project(session, project_id, organization_id)
            if project is None:
                return 0
            rows = list(session.scalars(select(AIConsent).where(AIConsent.project_id == project.id, AIConsent.organization_id == stable_uuid(organization_id), AIConsent.document_id == document_id, AIConsent.revoked_at.is_(None))))
            for row in rows:
                row.revoked_at = datetime.now(timezone.utc)
            return len(rows)

    def get_project(self, project_id: str, organization_id: str = "org_demo") -> dict[str, Any] | None:
        with self.session_factory() as session:
            project = self._find_project(session, project_id, organization_id)
            return self._project_dict(project) if project else None

    def list_releases(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        with self.session_factory() as session:
            project = self._find_project(session, project_id, organization_id)
            if project is None:
                return []
            project_key = (project.metadata_json or {}).get("canonical_id", project.slug)
            return [self._release_dict(item, project_key) for item in session.scalars(select(DeliveryRelease).where(DeliveryRelease.project_id == project.id))]

    def dashboard(self, project_id: str, release_id: str, organization_id: str = "org_demo") -> dict[str, Any] | None:
        with self.session_factory() as session:
            project = self._find_project(session, project_id, organization_id)
            if project is None:
                return None
            release = session.scalar(select(DeliveryRelease).where(DeliveryRelease.id == stable_uuid(release_id), DeliveryRelease.project_id == project.id))
            if release is None:
                return None
            return project.metadata_json.get("dashboard") if project.metadata_json else None

    def _project_metadata(self, project_id: str, organization_id: str, key: str) -> Any:
        with self.session_factory() as session:
            project = self._find_project(session, project_id, organization_id)
            return (project.metadata_json or {}).get(key, []) if project else []

    def requirements(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        return list(self._project_metadata(project_id, organization_id, "requirements"))

    def changes(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        return list(self._project_metadata(project_id, organization_id, "changes"))

    def scope_versions(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        return list(self._project_metadata(project_id, organization_id, "scope_versions"))

    def attention(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        return list(self._project_metadata(project_id, organization_id, "attention"))

    def acceptance(self, project_id: str, organization_id: str = "org_demo") -> list[dict[str, Any]]:
        return list(self._project_metadata(project_id, organization_id, "acceptance"))

    def delivery_pack(self, project_id: str, release_id: str, organization_id: str = "org_demo") -> dict[str, Any] | None:
        project = self.get_project(project_id, organization_id)
        if not project or project.get("release_id") != release_id:
            return None
        return self._project_metadata(project_id, organization_id, "delivery_pack") or None

    def save_agent_state(self, run: Any, steps: list[Any], checkpoints: list[Any], approvals: list[Any]) -> None:
        """Persist a run snapshot transactionally; no prompt or document content is stored."""
        with self.session_factory.begin() as session:
            run_id = stable_uuid(run.id)
            project = self._find_project(session, run.project_id, run.organization_id)
            if project is None:
                return
            record = session.get(DbAgentRun, run_id)
            if record is None:
                record = DbAgentRun(id=run_id, organization_id=stable_uuid(run.organization_id), project_id=project.id, agent_id=run.agent_id, provider=run.provider, model=run.model)
                session.add(record)
            record.status = run.status
            record.classification = run.classification
            record.current_step = run.current_step
            record.max_steps = run.max_steps
            record.input_json = {"length": len(run.input)}
            record.result_json = {"keys": sorted(run.result.keys())}
            record.error = run.error
            for step in steps:
                if session.get(DbAgentStep, stable_uuid(step.id)) is None:
                    session.add(DbAgentStep(id=stable_uuid(step.id), run_id=run_id, ordinal=step.ordinal, tool=step.tool, status=step.status, input_json=step.input, output_json=step.output if isinstance(step.output, dict) else {"value": step.output}, error=step.error, duration_ms=step.duration_ms))
            for checkpoint in checkpoints:
                if session.get(DbAgentCheckpoint, stable_uuid(checkpoint.id)) is None:
                    session.add(DbAgentCheckpoint(id=stable_uuid(checkpoint.id), run_id=run_id, ordinal=checkpoint.ordinal, state_json=checkpoint.state))
            for approval in approvals:
                approval_record = session.get(DbAgentApproval, stable_uuid(approval.id))
                if approval_record is None:
                    session.add(DbAgentApproval(id=stable_uuid(approval.id), organization_id=stable_uuid(run.organization_id), run_id=run_id, tool=approval.tool, reason=approval.reason, status=approval.status, decided_by=approval.decided_by, comment=approval.comment))
                else:
                    approval_record.status = approval.status
                    approval_record.decided_by = approval.decided_by
                    approval_record.comment = approval.comment

    @staticmethod
    def _project_dict(project: Project) -> dict[str, Any]:
        dashboard = project.metadata_json.get("dashboard", {}) if project.metadata_json else {}
        return {"id": project.metadata_json.get("canonical_id", project.slug) if project.metadata_json else project.slug, "organization_id": str(project.organization_id), "slug": project.slug, "name": project.name, "client": project.client, "description": project.description, "release_id": project.metadata_json.get("release_id", "") if project.metadata_json else "", "release": dashboard.get("project", {}).get("release", ""), "baseline": "Persisted baseline", "status": dashboard.get("project", {}).get("status", "draft"), "requirements_count": project.metadata_json.get("requirements_count", len(dashboard.get("requirements", []))) if project.metadata_json else len(dashboard.get("requirements", []))}

    @staticmethod
    def _release_dict(release: DeliveryRelease, project_slug: str) -> dict[str, Any]:
        return {"id": release.metadata_json.get("slug", str(release.id)), "project_id": project_slug, "name": release.name, "version": release.version, "status": release.status, "created_at": release.created_at.isoformat() if release.created_at else "", "target_date": release.metadata_json.get("target_date", "") if release.metadata_json else "", "baseline": "Persisted baseline"}

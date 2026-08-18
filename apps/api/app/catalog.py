"""Canonical demo catalog and dashboard projections.

The web application does not own demo payloads.  Both demo projects are
represented here, behind the same project/release projection used by the
database repository in production mode.  Keeping this adapter small makes the
mock mode deterministic while preserving the domain boundaries of the API.
"""
from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5


ORG_ID = "org_demo"
ACME_PROJECT_ID = "project_acme"
ACME_RELEASE_ID = "release_2_3"
CUSTOMER_PROJECT_ID = "project_demo"
CUSTOMER_RELEASE_ID = "release_1_0"


def _acme_rows() -> list[dict[str, Any]]:
    exact = [
        {"id": "REQ-023", "title": "User can reset password", "status": "agreed", "verification": "passed", "coverage": 100},
        {"id": "REQ-041", "title": "Admin can export user data", "status": "agreed", "verification": "passed", "coverage": 100},
        {"id": "REQ-057", "title": "Two-factor authentication", "status": "agreed", "verification": "in_progress", "coverage": 80},
        {"id": "REQ-063", "title": "Audit log for data changes", "status": "agreed", "verification": "passed", "coverage": 100},
        {"id": "REQ-071", "title": "Support bulk user import", "status": "pending", "verification": "not_started", "coverage": 0},
    ]
    filler = [
        ("Password policy enforcement", "agreed", "passed", 100),
        ("Admin session timeout", "agreed", "passed", 100),
        ("User invitation flow", "agreed", "passed", 100),
        ("Role permissions matrix", "agreed", "passed", 100),
        ("Export audit trail", "agreed", "passed", 100),
        ("Bulk import validation", "pending", "not_started", 0),
    ]
    rows = list(exact)
    for index in range(6, 87):
        title, status, verification, coverage = filler[(index - 6) % len(filler)]
        rows.append({"id": f"REQ-{index:03d}", "title": title, "status": status, "verification": verification, "coverage": coverage})
    return rows


def _acme_project() -> dict[str, Any]:
    return {
        "id": ACME_PROJECT_ID,
        "organization_id": ORG_ID,
        "slug": "acme",
        "name": "Acme Inc.",
        "client": "Acme Inc.",
        "description": "Client Portal delivery assurance workspace.",
        "release_id": ACME_RELEASE_ID,
        "release": "Release 2.3",
        "baseline": "BR-1.4 · approved",
        "status": "in_signoff",
        "requirements_count": 86,
    }


def _customer_project(store: Any) -> dict[str, Any]:
    return {
        "id": CUSTOMER_PROJECT_ID,
        "organization_id": ORG_ID,
        "slug": "customer-operations",
        "name": store.project["name"],
        "client": store.project["client"],
        "description": "Functional end-to-end demo with Change Radar and File Inspector.",
        "release_id": CUSTOMER_RELEASE_ID,
        "release": "Release 1.0",
        "baseline": "Scope v1 · approved 14 Aug 2026",
        "status": store.project.get("status", "pending_acceptance"),
        "requirements_count": len(store.requirements),
    }


def _release(project: dict[str, Any], *, release_id: str, name: str, version: str, status: str, created_at: str, target_date: str, baseline: str) -> dict[str, Any]:
    return {
        "id": release_id,
        "project_id": project["id"],
        "name": name,
        "version": version,
        "status": status,
        "created_at": created_at,
        "target_date": target_date,
        "baseline": baseline,
    }


def _acme_detail(row: dict[str, Any]) -> dict[str, Any]:
    if row["id"] == "REQ-041":
        return {
            "id": "REQ-041", "status": "agreed", "version": "v1.2", "title": "Admin can export user data",
            "description": "As an admin, I want to export user data in CSV format so that I can perform external analysis.",
            "type": "Functional", "priority": "High", "component": "User Management", "baseline": "BR-1.4",
            "created": "Apr 18, 2025", "agreed": "Apr 22, 2025", "owner": "María López",
            "criteria": [
                "Export includes all user fields as defined in the data dictionary",
                "CSV file is downloadable from the admin panel",
                "Export includes data filters (date range, role, status)",
                "System handles up to 10k records per export",
            ],
        }
    return {
        "id": row["id"], "status": row["status"], "version": "v1.0", "title": row["title"],
        "description": f"The delivery must demonstrate: {row['title']}.", "type": "Functional", "priority": "Medium",
        "component": "Client Portal", "baseline": "BR-1.4", "created": "Apr 18, 2025", "agreed": "Apr 22, 2025",
        "owner": "María López", "criteria": [f"The {row['title'].lower()} flow is available", "The expected outcome is visible to the client"],
    }


def _customer_dashboard(store: Any) -> dict[str, Any]:
    requirements = []
    for item in store.requirements:
        requirements.append({
            "id": item.human_id,
            "title": item.title,
            "status": "agreed" if item.status == "demonstrated" else "pending",
            "verification": "passed" if item.status == "demonstrated" else "in_progress" if item.status == "partially_demonstrated" else "not_started",
            "coverage": 100 if item.status == "demonstrated" else 60 if item.status == "partially_demonstrated" else 0,
        })
    selected = requirements[0]
    selected_requirement = {
        "id": selected["id"], "status": selected["status"], "version": "v1.0", "title": selected["title"],
        "description": next(item.description for item in store.requirements if item.human_id == selected["id"]),
        "type": "Functional", "priority": "High", "component": "Operations Portal", "baseline": "Scope v1",
        "created": "Aug 14, 2026", "agreed": "Aug 14, 2026", "owner": "Demo Owner",
        "criteria": [item.text for item in next(item for item in store.requirements if item.human_id == selected["id"]).criteria],
    }
    demonstrated = sum(item.status == "demonstrated" for item in store.requirements)
    partial = sum(item.status == "partially_demonstrated" for item in store.requirements)
    not_demonstrated = len(store.requirements) - demonstrated - partial
    return {
        "project": {
            "id": CUSTOMER_PROJECT_ID, "name": store.project["name"], "client": store.project["client"], "release": "Release 1.0",
            "version": "1.0.0", "status": store.project.get("status", "pending_acceptance"), "created_at": "2026-08-14T00:00:00Z", "target_date": "2026-08-28T00:00:00Z",
        },
        "metrics": {
            "requirements": {"value": len(store.requirements), "items": [{"value": demonstrated, "tone": "success", "label": "demonstrated"}, {"value": partial, "tone": "warning", "label": "partial"}, {"value": not_demonstrated, "tone": "neutral", "label": "pending"}]},
            "verification": {"value": round((demonstrated / len(store.requirements)) * 100), "suffix": "%", "items": [{"value": demonstrated, "tone": "success", "label": "passed"}, {"value": not_demonstrated, "tone": "error", "label": "failed"}, {"value": partial, "tone": "progress", "label": "in progress"}]},
            "coverage": {"value": round(((demonstrated + partial) / len(store.requirements)) * 100), "suffix": "%", "items": [{"value": 4, "tone": "success", "label": "vs last release"}]},
            "changes": {"value": len(store.changes), "items": [{"value": sum(item.status == "approved" for item in store.changes), "tone": "success", "label": "approved"}, {"value": sum(item.status == "proposed" for item in store.changes), "tone": "warning", "label": "pending"}, {"value": 0, "tone": "error", "label": "rejected"}]},
        },
        "requirements": requirements[:5],
        "selected_requirement": selected_requirement,
        "activity": [{"avatar": "system", "author": "System", "text": "verified the demo requirements", "time": "Today"}, {"avatar": "maria", "author": "Demo Owner", "text": "approved Scope v1", "time": "2d ago"}],
        "verification_status": [{"name": "Passed", "value": demonstrated, "tone": "success"}, {"name": "Failed", "value": not_demonstrated, "tone": "error"}, {"name": "In progress", "value": partial, "tone": "progress"}, {"name": "Not started", "value": 0, "tone": "neutral"}],
        "coverage_trend": [42, 48, 53, 59, 64, 72, 78, 83],
    }


class ProjectCatalog:
    """Single read model for project, release and dashboard context."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.acme = _acme_project()
        self.customer = _customer_project(store)

    def list_projects(self, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        return [self.acme, self.customer] if organization_id == ORG_ID else []

    def get_project(self, project_id: str, organization_id: str = ORG_ID) -> dict[str, Any] | None:
        return next((item for item in self.list_projects(organization_id) if item["id"] == project_id), None)

    def list_releases(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        project = self.get_project(project_id, organization_id)
        if not project:
            return []
        if project_id == ACME_PROJECT_ID:
            return [_release(project, release_id=ACME_RELEASE_ID, name="Release 2.3", version="2.3.0", status="in_signoff", created_at="2025-05-12T00:00:00Z", target_date="2025-05-30T00:00:00Z", baseline="BR-1.4")]
        return [_release(project, release_id=CUSTOMER_RELEASE_ID, name="Release 1.0", version="1.0.0", status="pending_acceptance", created_at="2026-08-14T00:00:00Z", target_date="2026-08-28T00:00:00Z", baseline="Scope v1")]

    def get_release(self, project_id: str, release_id: str, organization_id: str = ORG_ID) -> dict[str, Any] | None:
        return next((item for item in self.list_releases(project_id, organization_id) if item["id"] == release_id), None)

    def dashboard(self, project_id: str, release_id: str, organization_id: str = ORG_ID) -> dict[str, Any] | None:
        if not self.get_release(project_id, release_id, organization_id):
            return None
        if project_id == ACME_PROJECT_ID:
            rows = _acme_rows()
            selected = next(item for item in rows if item["id"] == "REQ-041")
            return {
                "project": {"id": ACME_PROJECT_ID, "name": "Acme Inc.", "client": "Acme Inc.", "release": "Release 2.3", "version": "2.3.0", "status": "in_signoff", "created_at": "2025-05-12T00:00:00Z", "target_date": "2025-05-30T00:00:00Z"},
                "metrics": {"requirements": {"value": 86, "items": [{"value": 74, "tone": "success", "label": "agreed"}, {"value": 8, "tone": "warning", "label": "pending"}, {"value": 4, "tone": "neutral", "label": "out of scope"}]}, "verification": {"value": 82, "suffix": "%", "items": [{"value": 71, "tone": "success", "label": "passed"}, {"value": 11, "tone": "error", "label": "failed"}, {"value": 4, "tone": "progress", "label": "in progress"}]}, "coverage": {"value": 95, "suffix": "%", "items": [{"value": 6, "tone": "success", "label": "vs last release"}]}, "changes": {"value": 12, "items": [{"value": 8, "tone": "success", "label": "approved"}, {"value": 2, "tone": "warning", "label": "pending"}, {"value": 2, "tone": "error", "label": "rejected"}]}},
                "requirements": rows[:5], "selected_requirement": _acme_detail(selected),
                "activity": [{"avatar": "maria", "author": "María López", "text": "approved change CHG-021", "time": "2h ago"}, {"avatar": "system", "author": "System", "text": "verified 5 requirements", "time": "5h ago"}, {"avatar": "john", "author": "John Smith", "text": "commented on REQ-041", "time": "1d ago"}],
                "verification_status": [{"name": "Passed", "value": 71, "tone": "success"}, {"name": "Failed", "value": 11, "tone": "error"}, {"name": "In progress", "value": 4, "tone": "progress"}, {"name": "Not started", "value": 4, "tone": "neutral"}],
                "coverage_trend": [68, 70, 69, 71, 73, 72, 74, 77, 79, 82, 88, 95],
            }
        return _customer_dashboard(self.store)

    def requirements(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        if not self.get_project(project_id, organization_id):
            return []
        if project_id == ACME_PROJECT_ID:
            rows = _acme_rows()
            selected = next(item for item in rows if item["id"] == "REQ-041")
            details = {selected["id"]: _acme_detail(selected)}
            return [{"id": str(uuid5(NAMESPACE_URL, f"sda:{project_id}:{row['id']}")), "human_id": row["id"], "title": row["title"], "description": details.get(row["id"], {}).get("description", f"The delivery must demonstrate: {row['title']}"), "category": "Functional", "priority": "high" if row["id"] in {"REQ-023", "REQ-041"} else "medium", "status": "demonstrated" if row["status"] == "agreed" else "not_demonstrated", "confidence": 0.95, "source": "Acme Client Portal Baseline", "criteria": [{"id": str(uuid5(NAMESPACE_URL, f"sda:{project_id}:{row['id']}:criterion:{index}")), "text": criterion, "type": "semantic", "automated": True} for index, criterion in enumerate(details.get(row["id"], {}).get("criteria", [f"The {row['title'].lower()} outcome is observable"]), 1)]} for row in rows]
        return [item.model_dump() for item in self.store.requirements]

    def changes(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        if not self.get_project(project_id, organization_id):
            return []
        if project_id == ACME_PROJECT_ID:
            return [{"id": str(uuid5(NAMESPACE_URL, f"sda:{project_id}:change:{index}")), "title": f"Release change {index:02d}", "original": "Approved release baseline", "proposed": "Tracked delivery adjustment", "classification": "possible_scope_change" if index % 3 == 0 else "clarification", "status": "approved" if index <= 8 else "proposed" if index <= 10 else "rejected", "impact": "Medium"} for index in range(1, 13)]
        return [item.model_dump() for item in self.store.changes]

    def scope_versions(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        if not self.get_project(project_id, organization_id):
            return []
        if project_id == ACME_PROJECT_ID:
            return [{"version": "BR-1.4", "status": "approved", "source": "Acme Client Portal Agreement", "summary": "Frozen baseline for Release 2.3.", "created_at": "2025-04-18T10:00:00Z", "created_by": "demo.owner"}]
        return self.store.scope_versions

    def attention(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        if not self.get_project(project_id, organization_id):
            return []
        if project_id == ACME_PROJECT_ID:
            return [{"severity": "critical", "title": "11 verification results failed", "source": "Verification"}, {"severity": "warning", "title": "2 changes are pending decision", "source": "Change Radar"}, {"severity": "info", "title": "8 requirements are accepted", "source": "Client acceptance"}]
        return [{"severity": "critical", "title": "Performance budget is not demonstrated", "source": "Verification"}, {"severity": "warning", "title": "Warehouse manager role is an unapproved scope change", "source": "Change Radar"}, {"severity": "warning", "title": "Email alerts have unresolved client comments", "source": "Acceptance"}, {"severity": "info", "title": "8 requirements have been accepted", "source": "Client Portal"}]

    def acceptance(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        if not self.get_project(project_id, organization_id):
            return []
        if project_id == ACME_PROJECT_ID:
            return [{"requirement_id": str(uuid5(NAMESPACE_URL, f"sda:{project_id}:{row['id']}")), "human_id": row["id"], "decision": "accepted" if index <= 8 else "pending", "comment": ""} for index, row in enumerate(_acme_rows()[:12], 1)]
        return self.store.acceptance

    def delivery_pack(self, project_id: str, release_id: str, organization_id: str = ORG_ID) -> dict[str, Any] | None:
        projection = self.dashboard(project_id, release_id, organization_id)
        if not projection:
            return None
        requirements = self.requirements(project_id, organization_id)
        return {"release": projection["project"]["release"], "project": projection["project"], "story": {"promised": "The approved release baseline.", "delivered": f"{sum(item['verification'] == 'passed' for item in projection['requirements'])} visible requirements demonstrated.", "changed": f"{len(self.changes(project_id, organization_id))} changes tracked.", "remaining": "Review failed, partial and pending items.", "approval": "Client acceptance is pending."}, "requirements": requirements, "evidence": [{"id": str(uuid5(NAMESPACE_URL, f"sda:{project_id}:evidence:{row['id']}")), "artifact": f"{row['id'].lower()}-verification.png", "summary": "Verification evidence linked to the requirement."} for row in projection["requirements"]], "generated_at": "2026-08-18T00:00:00Z"}

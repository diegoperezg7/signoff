"""Project catalog facade over the live demo store.

The facade keeps the method names used by ``main.py``, the PostgreSQL
repository bootstrap and the tests. Every result is computed from the facts in
``store.projects`` through ``projections``; nothing here is a literal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import projections as P
from .seed import ACME_PROJECT_ID, ACME_RELEASE_ID, CUSTOMER_PROJECT_ID, CUSTOMER_RELEASE_ID, ORG_ID  # noqa: F401  (re-exported)


class ProjectCatalog:
    """Single read model for project, release and dashboard context."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def _state(self, project_id: str, organization_id: str = ORG_ID):
        state = self.store.projects.get(project_id)
        if state is None or state.project["organization_id"] != organization_id:
            return None
        return state

    def _proposals(self) -> list[dict[str, Any]]:
        return list(self.store.proposals.values())

    def list_projects(self, organization_id: str = ORG_ID, locale: str = "en") -> list[dict[str, Any]]:
        return [P.project_view(state, locale) for state in self.store.projects.values() if state.project["organization_id"] == organization_id]

    def get_project(self, project_id: str, organization_id: str = ORG_ID, locale: str = "en") -> dict[str, Any] | None:
        state = self._state(project_id, organization_id)
        return P.project_view(state, locale) if state else None

    def list_releases(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        return [P.release_view(state)] if state else []

    def get_release(self, project_id: str, release_id: str, organization_id: str = ORG_ID) -> dict[str, Any] | None:
        return next((item for item in self.list_releases(project_id, organization_id) if item["id"] == release_id), None)

    def dashboard(self, project_id: str, release_id: str, organization_id: str = ORG_ID, locale: str = "en") -> dict[str, Any] | None:
        state = self._state(project_id, organization_id)
        if not state or state.release["id"] != release_id:
            return None
        return P.dashboard(state, self._proposals(), list(self.store.audit_events), locale)

    def requirements(self, project_id: str, organization_id: str = ORG_ID, locale: str = "en") -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        return P.requirement_rows(state, locale) if state else []

    def changes(self, project_id: str, organization_id: str = ORG_ID, locale: str = "en") -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        return [P.change_view(state, item, locale) for item in state.changes] if state else []

    def scope_versions(self, project_id: str, organization_id: str = ORG_ID, locale: str = "en") -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        if not state:
            return []
        return [P.scope_version_view(state, item, locale) for item in sorted(state.scope_versions, key=lambda item: item["created_at"], reverse=True)]

    def attention(self, project_id: str, organization_id: str = ORG_ID, locale: str = "en") -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        return P.attention(state, self._proposals(), locale) if state else []

    def acceptance(self, project_id: str, organization_id: str = ORG_ID) -> list[dict[str, Any]]:
        state = self._state(project_id, organization_id)
        if not state:
            return []
        return [{"requirement_id": item["uuid"], "human_id": item["id"], "decision": item["acceptance"], "comment": item.get("acceptance_comment", "")} for item in state.requirements]

    def delivery_pack(self, project_id: str, release_id: str, organization_id: str = ORG_ID, locale: str = "en") -> dict[str, Any] | None:
        state = self._state(project_id, organization_id)
        if not state or state.release["id"] != release_id:
            return None
        return P.delivery_pack(state, locale, datetime.now(timezone.utc).isoformat())

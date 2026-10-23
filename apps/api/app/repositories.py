"""Repository boundary for tenant-scoped persistence."""
from __future__ import annotations

from typing import Any, Protocol


class Repository(Protocol):
    def get_project(self, organization_id: str, project_id: str) -> dict[str, Any] | None: ...
    def list_requirements(self, organization_id: str, project_id: str) -> list[dict[str, Any]]: ...
    def append_audit_event(self, organization_id: str, event: dict[str, Any]) -> None: ...


class InMemoryRepository:
    """Compatibility adapter used by mock mode and deterministic CI."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def get_project(self, organization_id: str, project_id: str) -> dict[str, Any] | None:
        return self.store.project if project_id == self.store.project["id"] else None

    def list_requirements(self, organization_id: str, project_id: str) -> list[dict[str, Any]]:
        return [item.model_dump() for item in self.store.requirements] if project_id == self.store.project["id"] else []

    def append_audit_event(self, organization_id: str, event: dict[str, Any]) -> None:
        self.store.audit_events.append({"organization_id": organization_id, **event})

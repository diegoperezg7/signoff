"""Job runner boundary shared by inline mock mode and Redis deployments."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4


class JobRunner(Protocol):
    def enqueue(self, kind: str, payload: dict[str, Any]) -> str: ...
    def retry(self, job_id: str) -> str: ...
    def cancel(self, job_id: str) -> None: ...
    def get_status(self, job_id: str) -> dict[str, Any]: ...


class InlineJobRunner:
    """Deterministic runner for MOCK_MODE and CI."""

    def __init__(self, handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None) -> None:
        self.handlers = handlers or {}
        self.jobs: dict[str, dict[str, Any]] = {}

    def enqueue(self, kind: str, payload: dict[str, Any]) -> str:
        job_id = f"job_{uuid4().hex[:12]}"
        self.jobs[job_id] = {"job_id": job_id, "kind": kind, "status": "queued", "payload": payload, "created_at": datetime.now(timezone.utc).isoformat()}
        handler = self.handlers.get(kind)
        if handler:
            try:
                self.jobs[job_id].update({"status": "completed", "result": handler(payload)})
            except Exception as exc:  # pragma: no cover - exercised by retry integration tests
                self.jobs[job_id].update({"status": "failed", "error": str(exc)})
        return job_id

    def retry(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return self.enqueue(job["kind"], job["payload"])

    def cancel(self, job_id: str) -> None:
        if job_id in self.jobs and self.jobs[job_id]["status"] in {"queued", "running"}:
            self.jobs[job_id]["status"] = "cancelled"

    def get_status(self, job_id: str) -> dict[str, Any]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

"""Dramatiq workers for long-running SDA operations.

Actors are deliberately idempotent by ``job_id``.  The API can enqueue these
jobs when ``SDA_JOB_MODE=redis``; mock mode keeps the same payloads and state
transitions available for local development and CI.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import dramatiq
from dramatiq.brokers.redis import RedisBroker


broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
dramatiq.set_broker(broker)
JOB_STATUS: dict[str, dict[str, Any]] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update(job_id: str, status: str, **extra: Any) -> None:
    JOB_STATUS[job_id] = {"job_id": job_id, "status": status, "updated_at": now(), **extra}
    print(json.dumps({"event": "sda_job", **JOB_STATUS[job_id]}, ensure_ascii=False))


def begin(job_id: str, kind: str) -> bool:
    current = JOB_STATUS.get(job_id)
    if current and current.get("status") == "completed":
        return False
    update(job_id, "running", kind=kind)
    return True


@dramatiq.actor(max_retries=2, time_limit=15 * 60 * 1000)
def run_verification(run_id: str, project_id: str, requirement_id: str) -> None:
    if not begin(run_id, "verification"):
        return
    time.sleep(0.01)
    update(run_id, "completed", project_id=project_id, requirement_id=requirement_id, result_state="manual_review_required", artifacts=[])


@dramatiq.actor(max_retries=2, time_limit=10 * 60 * 1000)
def extract_scope(document_id: str, project_id: str, job_id: str | None = None) -> None:
    identifier = job_id or f"scope:{document_id}"
    if not begin(identifier, "scope_extraction"):
        return
    update(identifier, "completed", document_id=document_id, project_id=project_id, proposal_status="draft", requirements_found=0)


@dramatiq.actor(max_retries=2, time_limit=10 * 60 * 1000)
def run_ai_task(job_id: str, project_id: str, task: str, context: dict[str, Any]) -> None:
    if not begin(job_id, "ai"):
        return
    update(job_id, "completed", project_id=project_id, task=task, proposal_status="draft", context_keys=sorted(context.keys()))


@dramatiq.actor(max_retries=2, time_limit=10 * 60 * 1000)
def inspect_file(job_id: str, project_id: str, filename: str, requirement_id: str | None = None) -> None:
    if not begin(job_id, "file_inspection"):
        return
    update(job_id, "completed", project_id=project_id, filename=filename, requirement_id=requirement_id, assessment="manual_review_required")


@dramatiq.actor(max_retries=2, time_limit=10 * 60 * 1000)
def generate_delivery_pack(job_id: str, project_id: str, release_id: str) -> None:
    if not begin(job_id, "delivery_pack"):
        return
    update(job_id, "completed", project_id=project_id, release_id=release_id, formats=["web", "json", "pdf", "zip"])


if __name__ == "__main__":
    print("SDA worker ready")

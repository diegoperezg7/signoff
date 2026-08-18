"""Transactional email boundary for Signoff alerts.

The provider never receives agreement text, prompts, credentials or evidence
contents. Alert emails contain only a short event summary and a deep link.
Mock mode records deliveries without contacting the network.
"""
from __future__ import annotations

import os
from typing import Any, Protocol
from uuid import uuid4

import httpx


class EmailProvider(Protocol):
    provider_name: str

    def send_agent_alert(self, *, to: str, agent_name: str, status: str, run_id: str, project_id: str, action_url: str) -> dict[str, Any]: ...


def _payload(*, to: str, agent_name: str, status: str, run_id: str, project_id: str, action_url: str, from_address: str) -> dict[str, Any]:
    safe_status = status.replace("_", " ").title()
    return {
        "from": from_address,
        "to": [to],
        "subject": f"Signoff agent update · {safe_status}",
        "html": f"<div style='font-family:Arial,sans-serif;max-width:560px'><h2>Signoff agent update</h2><p><strong>{agent_name}</strong> finished a run with status <strong>{safe_status}</strong>.</p><p>Run: <code>{run_id}</code><br/>Project: <code>{project_id}</code></p><p><a href='{action_url}'>Open Signoff</a></p></div>",
    }


class MockEmailProvider:
    provider_name = "mock"

    def __init__(self, deliveries: list[dict[str, Any]]) -> None:
        self.deliveries = deliveries

    def send_agent_alert(self, **kwargs: Any) -> dict[str, Any]:
        delivery = {"id": f"email_{uuid4().hex[:12]}", "provider": self.provider_name, "status": "mocked", "to": kwargs["to"], "event": "agent_alert", "run_id": kwargs["run_id"]}
        self.deliveries.append(delivery)
        return delivery


class ResendEmailProvider:
    provider_name = "resend"

    def __init__(self, deliveries: list[dict[str, Any]]) -> None:
        self.deliveries = deliveries
        self.api_key = os.getenv("RESEND_API_KEY", "")
        self.from_address = os.getenv("RESEND_FROM_EMAIL", "Signoff <onboarding@resend.dev>")
        self.reply_to = os.getenv("RESEND_REPLY_TO", "")

    def send_agent_alert(self, **kwargs: Any) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("RESEND_API_KEY is required for Resend email delivery")
        body = _payload(from_address=self.from_address, **kwargs)
        if self.reply_to:
            body["reply_to"] = self.reply_to
        response = httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=body, timeout=10)
        response.raise_for_status()
        result = response.json()
        delivery = {"id": result.get("id", f"email_{uuid4().hex[:12]}"), "provider": self.provider_name, "status": "sent", "to": kwargs["to"], "event": "agent_alert", "run_id": kwargs["run_id"]}
        self.deliveries.append(delivery)
        return delivery


def build_email_provider(deliveries: list[dict[str, Any]]) -> EmailProvider:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return MockEmailProvider(deliveries)
    return ResendEmailProvider(deliveries)

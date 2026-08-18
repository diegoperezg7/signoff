from fastapi.testclient import TestClient

from app.main import app, store


client = TestClient(app)


def test_agent_catalog_exposes_tools_and_safe_default_policy():
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["items"]} >= {"delivery-analyst", "change-radar"}
    assert {item["id"] for item in payload["tools"]} >= {"get_delivery_readiness", "record_acceptance_decision"}
    assert payload["policy"]["mode"] == "max_autonomy"
    assert "critical" not in payload["policy"]["allowed_risks"]


def test_agent_run_persists_steps_and_checkpoints_with_tenant_scope():
    response = client.post(
        "/api/v1/projects/project_demo/agents/run",
        json={"agent_id": "delivery-analyst", "input": "Explain the current blockers"},
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["current_step"] == 3
    assert len(run["checkpoint_ids"]) == 3

    detail = client.get(f"/api/v1/agent-runs/{run['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["steps"]) == 3
    assert len(detail.json()["checkpoints"]) == 3
    assert detail.json()["run"]["organization_id"] == "org_demo"

    listed = client.get("/api/v1/projects/project_demo/agents/runs")
    assert any(item["id"] == run["id"] for item in listed.json()["items"])


def test_policy_can_block_a_tool_and_writes_audit_event():
    original = store.agent_policies.get("org_demo")
    try:
        updated = client.patch("/api/v1/agent-policy", json={"blocked_tools": ["list_attention_items"], "max_steps": 8}).json()
        assert updated["blocked_tools"] == ["list_attention_items"]
        denied = client.post("/api/v1/projects/project_demo/agents/run", json={"agent_id": "delivery-analyst"})
        assert denied.status_code == 403
        assert any(event["event"] == "agent_policy_updated" for event in store.audit_events)
    finally:
        if original is None:
            store.agent_policies.pop("org_demo", None)
        else:
            store.agent_policies["org_demo"] = original


def test_approval_endpoint_is_tenant_aware():
    response = client.post(
        "/api/v1/projects/project_demo/agents/run",
        json={"agent_id": "requirements-coach", "requirement_id": "REQ-006"},
    )
    assert response.status_code == 200
    proposal_id = response.json()["proposal_id"]
    assert proposal_id
    assert client.post(f"/api/v1/ai/proposals/{proposal_id}/approve").status_code == 200


def test_agent_email_alert_uses_mock_provider_without_network():
    response = client.post("/api/v1/projects/project_demo/agents/run", json={"agent_id": "delivery-analyst"})
    assert response.status_code == 200
    run_id = response.json()["id"]
    alert = client.post(f"/api/v1/agent-runs/{run_id}/email-alert", json={"to": "reviewer@example.com"})
    assert alert.status_code == 200
    assert alert.json()["delivery"]["provider"] == "mock"
    assert alert.json()["delivery"]["status"] == "mocked"

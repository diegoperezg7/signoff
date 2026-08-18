from fastapi.testclient import TestClient

from app.main import app
from app.qa_explorer import QAExplorer


client = TestClient(app)


def test_qa_explorer_blocks_external_hosts():
    explorer = QAExplorer()
    try:
        explorer.discover("https://example.com")
    except ValueError as exc:
        assert "allowed local hosts" in str(exc)
    else:
        raise AssertionError("external host was not blocked")


def test_dispatch_routes_qa_question_to_qa_explorer(monkeypatch):
    class FakeExplorer:
        def discover(self, target_url, max_routes=20):
            return {"target_url": target_url, "routes": [target_url]}

        def smoke_check(self, target_url, routes=None, max_steps=12):
            return {"target_url": target_url, "routes_checked": len(routes or []), "observations": [{"passed": True}], "state": "demonstrated"}

    monkeypatch.setattr("app.main.qa_explorer", FakeExplorer())
    response = client.post(
        "/api/v1/projects/project_demo/agents/dispatch",
        json={
            "input": "Comprueba errores y funcionalidades de la app",
            "target_url": "http://localhost:3000/dashboard",
            "routes": ["http://localhost:3000/dashboard"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"]["id"] == "qa-explorer"
    assert payload["result"]["run_smoke_check"]["routes_checked"] == 1
    assert payload["result"]["run_smoke_check"]["observations"][0]["passed"] is True


def test_qa_run_links_observation_artifact(monkeypatch):
    class FakeExplorer:
        def discover(self, target_url, max_routes=20):
            return {"target_url": target_url, "routes": [target_url]}

        def smoke_check(self, target_url, routes=None, max_steps=12):
            return {"target_url": target_url, "routes_checked": 1, "observations": [{"passed": True}], "state": "demonstrated"}

    monkeypatch.setattr("app.main.qa_explorer", FakeExplorer())
    response = client.post("/api/v1/projects/project_demo/agents/run", json={"agent_id": "qa-explorer", "target_url": "http://localhost:3000/dashboard", "routes": ["http://localhost:3000/dashboard"]})
    assert response.status_code == 200
    result = response.json()["result"]["run_smoke_check"]
    assert result["evidence_artifact"].startswith("agent-runs/")
    assert len(result["evidence_sha256"]) == 64


def test_project_intelligence_answers_with_grounding_metadata():
    response = client.post("/api/v1/projects/project_demo/intelligence/ask", json={"question": "What is blocking acceptance?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["citations"]
    assert payload["provider"] == "MockLLMProvider"


def test_agreement_and_evidence_agents_use_shared_project_context():
    agreement = client.post("/api/v1/projects/project_demo/agents/run", json={"agent_id": "agreement-analyst"})
    evidence = client.post("/api/v1/projects/project_demo/agents/run", json={"agent_id": "evidence-curator"})
    assert agreement.status_code == 200
    assert evidence.status_code == 200
    assert agreement.json()["result"]["inspect_scope"]["active_version"]["version"] == "v1"
    assert evidence.json()["result"]["list_evidence"]

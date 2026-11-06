"""Every action must be reflected in every derived view."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import wait_for_run

client = TestClient(app)
ACME = "/api/v1/projects/project_acme"
DEMO = "/api/v1/projects/project_demo"

pytestmark = pytest.mark.usefixtures("fresh_store")


def dashboard(base: str = ACME, release: str = "release_2_3", locale: str = "en") -> dict:
    return client.get(f"{base}/releases/{release}/dashboard?locale={locale}").json()


def metric(data: dict, name: str, key: str) -> int:
    return next(item["value"] for item in data["metrics"][name]["items"] if item["key"] == key)


def attention_count(base: str, item_id: str) -> int:
    return next((item["count"] for item in client.get(f"{base}/attention").json() if item["id"] == item_id), 0)


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append({"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])})
    return events


@pytest.mark.parametrize("base,release", [(ACME, "release_2_3"), (DEMO, "release_1_0")])
def test_dashboard_metrics_match_requirement_rows(base, release):
    rows = client.get(f"{base}/requirements").json()
    data = dashboard(base, release)
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert data["metrics"]["requirements"]["value"] == len(rows)
    for key in ("agreed", "pending", "out_of_scope"):
        assert metric(data, "requirements", key) == sum(row["scope_status"] == key for row in rows)
    in_scope = [row for row in rows if row["scope_status"] != "out_of_scope"]
    for key in ("passed", "failed", "in_progress", "not_started"):
        assert metric(data, "verification", key) == sum(row["verification"] == key for row in in_scope)
    assert data["metrics"]["verification"]["value"] == round(100 * metric(data, "verification", "passed") / len(in_scope))
    assert data["metrics"]["coverage"]["value"] == round(100 * sum(row["evidence_count"] > 0 for row in in_scope) / len(in_scope))
    assert data["coverage_trend"][-1]["value"] == data["metrics"]["coverage"]["value"]
    changes = client.get(f"{base}/changes").json()
    assert data["metrics"]["changes"]["value"] == len(changes)
    assert metric(data, "changes", "approved") == sum(item["status"] == "approved" for item in changes)
    readiness = client.get(f"{base}/readiness").json()
    assert readiness["unresolved_comments"] == sum(row["open_comments"] for row in rows)


def test_acme_seed_is_coherent():
    rows = client.get(f"{ACME}/requirements").json()
    assert len(rows) == 86
    assert {row["id"]: row["title"] for row in rows if row["id"] in {"REQ-023", "REQ-041", "REQ-057", "REQ-063", "REQ-071"}} == {
        "REQ-023": "User can reset password",
        "REQ-041": "Admin can export user data",
        "REQ-057": "Two-factor authentication",
        "REQ-063": "Audit log for data changes",
        "REQ-071": "Support bulk user import",
    }
    passed = [row for row in rows if row["verification"] == "passed"]
    assert all(row["evidence_count"] > 0 for row in passed)
    assert len(client.get(f"{ACME}/changes").json()) == 12
    assert len(dashboard()["coverage_trend"]) == 12
    spanish = client.get(f"{ACME}/requirements/REQ-041?locale=es").json()
    assert spanish["title"] == "El administrador puede exportar datos de usuarios"


def test_approving_a_change_updates_every_view():
    before = dashboard()
    readiness_before = client.get(f"{ACME}/readiness").json()
    change = next(item for item in client.get(f"{ACME}/changes").json() if item["code"] == "CHG-018")
    response = client.patch(f"{ACME}/changes/{change['id']}", json={"status": "approved"})
    assert response.status_code == 200
    assert response.json()["decided_by"]["kind"] == "member"
    after = dashboard()
    assert metric(after, "changes", "approved") == metric(before, "changes", "approved") + 1
    assert metric(after, "changes", "proposed") == metric(before, "changes", "proposed") - 1
    assert metric(after, "requirements", "pending") == metric(before, "requirements", "pending") - 4
    assert client.get(f"{ACME}/readiness").json()["unapproved_scope_changes"] == readiness_before["unapproved_scope_changes"] - 1
    assert attention_count(ACME, "proposed_changes") == 1
    assert client.get(f"{ACME}/activity").json()[0]["text"] == "approved change CHG-018"
    assert client.get(f"{ACME}/activity?locale=es").json()[0]["text"] == "aprobó el cambio CHG-018"
    assert client.get(f"{ACME}/requirements/REQ-071").json()["scope_status"] == "agreed"


def test_verification_run_updates_status_trend_and_readiness():
    before = dashboard()
    readiness_before = client.get(f"{ACME}/readiness").json()
    response = client.post(f"{ACME}/runs", json={"requirement_ids": ["REQ-033"]})
    assert response.status_code == 200
    body = response.json()
    assert body["runs"][0]["result"] == "passed"
    assert body["evidence"][0]["requirement_id"] == "REQ-033"
    after = dashboard()
    assert metric(after, "verification", "passed") == metric(before, "verification", "passed") + 1
    assert metric(after, "verification", "in_progress") == metric(before, "verification", "in_progress") - 1
    assert len(after["coverage_trend"]) == len(before["coverage_trend"]) + 1
    assert after["metrics"]["coverage"]["value"] >= before["metrics"]["coverage"]["value"]
    assert client.get(f"{ACME}/readiness").json()["demonstrated"] == readiness_before["demonstrated"] + 1
    detail = client.get(f"{ACME}/requirements/REQ-033").json()
    assert detail["runs"][0]["result"] == "passed"
    assert detail["evidence"][0]["id"] == body["evidence"][0]["id"]
    assert client.get(f"{ACME}/activity").json()[0]["text"] == "ran verification on 1 requirement: 1 passed, 0 failed"
    release = client.get(f"{ACME}/releases").json()["items"][0]
    assert release["verification"] == after["metrics"]["verification"]["value"]


def test_failed_verification_needs_a_fix():
    first = client.post(f"{ACME}/runs", json={"requirement_ids": ["REQ-021"]}).json()
    assert first["runs"][0]["result"] == "failed"
    assert attention_count(ACME, "failed_verifications") == 9


def test_uploading_evidence_updates_counts_and_readiness():
    readiness_before = client.get(f"{ACME}/readiness").json()
    csv = b"id,email,role\n1,a@acme.example,admin\n2,b@acme.example,viewer\n"
    response = client.post(f"{ACME}/evidence", data={"requirement_id": "REQ-039", "description": "Export API sample"}, files={"file": ("export.csv", csv, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert body["inspection"]["row_count"] == 2
    assert body["evidence"]["kind"] == "csv"
    assert body["evidence"]["source"] == "upload"
    assert len(body["evidence"]["sha256"]) == 64
    assert client.get(f"{ACME}/requirements/REQ-039").json()["evidence_count"] == 1
    assert client.get(f"{ACME}/readiness").json()["without_evidence"] == readiness_before["without_evidence"] - 1
    assert client.get(f"{ACME}/evidence").json()[0]["id"] == body["evidence"]["id"]
    assert client.get(f"{ACME}/activity").json()[0]["text"] == "uploaded export.csv for REQ-039"


def test_comments_persist_and_count_until_resolved():
    readiness_before = client.get(f"{ACME}/readiness").json()["unresolved_comments"]
    comment = client.post(f"{ACME}/requirements/REQ-023/comments", json={"text": "Please attach the reset email screenshot."}).json()
    assert comment["author"]["role"] == "owner"
    assert client.get(f"{ACME}/requirements/REQ-023").json()["open_comments"] == 1
    assert client.get(f"{ACME}/readiness").json()["unresolved_comments"] == readiness_before + 1
    assert attention_count(ACME, "open_comments") == readiness_before + 1
    assert client.get(f"{ACME}/activity").json()[0]["text"] == "commented on REQ-023"
    resolved = client.post(f"{ACME}/comments/{comment['id']}/resolve").json()
    assert resolved["resolved"] is True
    assert client.get(f"{ACME}/readiness").json()["unresolved_comments"] == readiness_before
    assert [item["id"] for item in client.get(f"{ACME}/requirements/REQ-023/comments").json()][-1] == comment["id"]


def test_approving_a_criteria_proposal_applies_it_and_fixes_the_defect():
    response = client.post(f"{ACME}/agents/run", json={"agent_id": "requirements-coach", "requirement_id": "REQ-021", "input": "Cover the retry schedule"})
    assert response.json()["status"] == "queued"
    run = wait_for_run(client, response.json()["run_id"])
    assert run["status"] == "requires_approval"
    assert dashboard()["pending_proposals"] == 1
    assert attention_count(ACME, "pending_proposals") == 1
    drafts = client.get(f"{ACME}/proposals?status=draft").json()
    assert [item["id"] for item in drafts] == [run["proposal_id"]]
    assert drafts[0]["kind"] == "criteria"
    before = client.get(f"{ACME}/requirements/REQ-021").json()["criteria_count"]
    approved = client.post(f"{ACME}/proposals/{run['proposal_id']}/approve").json()
    assert approved["proposal"]["status"] == "approved"
    assert approved["applied"][0]["id"] == "REQ-021"
    detail = client.get(f"{ACME}/requirements/REQ-021").json()
    assert detail["criteria_count"] > before
    assert any(item["text"] == "Covers the request: Cover the retry schedule" for item in detail["criteria"])
    assert client.get(f"/api/v1/agent-runs/{run['id']}").json()["status"] == "completed"
    assert dashboard()["pending_proposals"] == 0
    assert client.post(f"{ACME}/runs", json={"requirement_ids": ["REQ-021"]}).json()["runs"][0]["result"] == "passed"


def test_change_and_evidence_proposals_create_facts():
    change_run = wait_for_run(client, client.post(f"{ACME}/agents/run", json={"agent_id": "change-radar", "input": "Add scheduled export of invoices to SFTP"}).json()["run_id"])
    applied = client.post(f"/api/v1/ai/proposals/{change_run['proposal_id']}/approve").json()
    assert applied["status"] == "approved"
    changes = client.get(f"{ACME}/changes").json()
    created = next(item for item in changes if item["source"] == "agent")
    assert created["code"] == "CHG-022"
    assert created["status"] == "proposed"
    assert metric(dashboard(), "changes", "proposed") == 3

    comments_run = wait_for_run(client, client.post(f"{ACME}/agents/run", json={"agent_id": "agreement-analyst"}).json()["run_id"])
    open_before = client.get(f"{ACME}/readiness").json()["unresolved_comments"]
    result = client.post(f"{ACME}/proposals/{comments_run['proposal_id']}/approve").json()
    assert result["applied"]
    assert client.get(f"{ACME}/readiness").json()["unresolved_comments"] == open_before + len(result["applied"])


def test_rejecting_a_proposal_applies_nothing():
    run = wait_for_run(client, client.post(f"{DEMO}/agents/run", json={"agent_id": "verification-planner", "requirement_id": "REQ-010"}).json()["run_id"])
    rejected = client.post(f"{DEMO}/proposals/{run['proposal_id']}/reject", json={"comment": "Not now"}).json()
    assert rejected["proposal"]["status"] == "rejected"
    assert client.get(f"{DEMO}/requirements/REQ-010").json()["verification_plan"] is None
    assert client.get(f"/api/v1/agent-runs/{run['id']}").json()["status"] == "completed"


def test_portal_decision_changes_release_attention_and_activity():
    client.post(f"{ACME}/releases/release_2_3/send-for-acceptance")
    assert client.get("/api/v1/review/acme-review-token").json()["release_status"] == "ready"
    response = client.post("/api/v1/review/acme-review-token", json={"decision": "revision_requested", "comment": "Fix the failed exports"})
    assert response.status_code == 200
    assert dashboard()["project"]["status"] == "revision_requested"
    assert client.get(f"{ACME}/releases").json()["items"][0]["status"] == "revision_requested"
    assert client.get("/api/v1/projects").json()["items"][0]["status"] == "revision_requested"
    attention = client.get(f"{ACME}/attention").json()
    assert attention[0]["id"] == "client_decision" and attention[0]["severity"] == "critical"
    latest = client.get(f"{ACME}/activity").json()[0]
    assert latest["actor"]["kind"] == "client"
    assert latest["text"] == "requested a revision of the release"
    review = client.get("/api/v1/review/acme-review-token?locale=es").json()
    assert review["decision"]["comment"] == "Fix the failed exports"
    assert review["story"]["delivered"].startswith("66 de 82")
    assert client.get(f"{ACME}/requirements/REQ-021").json()["acceptance"] == "revision_requested"


def test_agent_events_stream_in_order_and_replay():
    run_id = client.post(f"{DEMO}/agents/run", json={"agent_id": "delivery-analyst", "input": "What blocks acceptance?"}).json()["run_id"]
    response = client.get(f"/api/v1/agent-runs/{run_id}/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [item["event"] for item in events] == ["run_started", "step_started", "step_completed", "step_started", "step_completed", "step_started", "step_completed", "proposal_created", "run_completed"]
    assert [item["id"] for item in events] == list(range(1, 10))
    assert len(events[0]["data"]["steps"]) == 3
    assert events[2]["data"]["summary"].startswith("Readiness")
    assert events[7]["data"]["proposal"]["kind"] == "report"
    assert events[8]["data"]["status"] == "requires_approval"
    replay = parse_sse(client.get(f"/api/v1/agent-runs/{run_id}/events?after=7").text)
    assert [item["event"] for item in replay] == ["proposal_created", "run_completed"]
    header_replay = parse_sse(client.get(f"/api/v1/agent-runs/{run_id}/events", headers={"Last-Event-ID": "8"}).text)
    assert [item["event"] for item in header_replay] == ["run_completed"]
    spanish = parse_sse(client.get(f"/api/v1/agent-runs/{run_id}/events?locale=es&after=3").text)
    assert spanish[0]["data"]["label"] == "Listar puntos de atención"
    runs = client.get(f"{DEMO}/agents/runs").json()["items"]
    assert runs[0]["id"] == run_id and runs[0]["agent"]["name"] == "Delivery analyst"


def test_agent_failure_is_a_failed_run_not_a_500():
    response = client.post(f"{DEMO}/agents/run", json={"agent_id": "qa-explorer", "target_url": "https://example.com"})
    assert response.status_code == 200
    run = wait_for_run(client, response.json()["run_id"])
    assert run["status"] == "failed"
    events = parse_sse(client.get(f"/api/v1/agent-runs/{run['id']}/events").text)
    assert events[-1]["event"] == "run_failed"
    assert "allowed local hosts" in events[-1]["data"]["error"]


def test_agent_audit_uses_the_run_id():
    run_id = client.post(f"{DEMO}/agents/run", json={"agent_id": "evidence-curator"}).json()["run_id"]
    wait_for_run(client, run_id)
    audit = client.get(f"{DEMO}/audit").json()
    assert any(item["event"] == "ai_agent_run_completed" and item["run_id"] == run_id for item in audit)
    assert all(item.get("project_id") == "project_demo" for item in audit)
    client.patch("/api/v1/agent-policy", json={"max_steps": 12})
    assert all(item.get("project_id") == "project_demo" for item in client.get(f"{DEMO}/audit").json())


def test_scope_extract_and_approve_adds_requirements_on_acme():
    text = "# Release 2.4 additions\n- Customer can download a usage statement\n- Admin can export user data\n2. Partner can view shared invoices\nREQ-053: Session expires after 20 minutes idle\n"
    draft = client.post(f"{ACME}/scope/extract", files={"file": ("addendum.txt", text.encode(), "text/plain")})
    assert draft.status_code == 200
    body = draft.json()
    assert body["version"] == "BR-1.5"
    assert body["status"] == "draft"
    assert [item["title"] for item in body["diff"]["added"]] == ["Customer can download a usage statement", "Partner can view shared invoices"]
    assert body["diff"]["modified"][0]["id"] == "REQ-053"
    approved = client.post(f"{ACME}/scope/versions/BR-1.5/approve").json()
    assert approved["status"] == "approved"
    versions = client.get(f"{ACME}/scope/versions").json()
    assert versions[0]["version"] == "BR-1.5"
    assert next(item for item in versions if item["version"] == "BR-1.4")["status"] == "superseded"
    rows = client.get(f"{ACME}/requirements").json()
    assert len(rows) == 88
    assert rows[-1]["id"] == "REQ-088" and rows[-1]["verification"] == "not_started" and rows[-1]["scope_status"] == "agreed"
    assert client.get(f"{ACME}/requirements/REQ-053").json()["title"] == "Session expires after 20 minutes idle"
    assert dashboard()["metrics"]["requirements"]["value"] == 88
    assert client.get(f"{ACME}/activity").json()[0]["text"] == "approved baseline BR-1.5"


def test_scope_extract_works_for_northstar_with_simulated_documents():
    draft = client.post(f"{DEMO}/scope/extract", files={"file": ("sow.pdf", b"%PDF-1.4 demo", "application/pdf")}).json()
    assert draft["version"] == "v2"
    assert len(draft["diff"]["added"]) == 3
    client.post(f"{DEMO}/scope/versions/v2/approve")
    assert len(client.get(f"{DEMO}/requirements").json()) == 15


def test_team_and_requirement_patch():
    team = client.get(f"{ACME}/team").json()
    assert team[0]["role"] == "owner"
    assert {item["role"] for item in team} == {"owner", "delivery_lead", "qa", "client_reviewer"}
    updated = client.patch(f"{ACME}/requirements/REQ-071", json={"scope_status": "agreed", "owner_id": team[2]["id"]}).json()
    assert updated["scope_status"] == "agreed"
    assert updated["owner"]["id"] == team[2]["id"]
    assert metric(dashboard(), "requirements", "pending") == 7


def test_component_names_follow_the_locale():
    english = client.get(f"{ACME}/requirements/REQ-041").json()
    spanish = client.get(f"{ACME}/requirements/REQ-041?locale=es").json()
    assert english["component"] == "Exports"
    assert spanish["component"] == "Exportaciones"
    assert spanish["component_key"] == "Exports"
    rows = {row["component_key"]: row["component"] for row in client.get(f"{ACME}/requirements?locale=es").json()}
    assert rows == {"Users": "Usuarios", "Billing": "Facturación", "Exports": "Exportaciones", "Notifications": "Notificaciones", "Security": "Seguridad", "Reporting": "Informes"}
    northstar = {row["component"] for row in client.get(f"{DEMO}/requirements?locale=es").json()}
    assert {"Autenticación", "Flujo principal", "Cumplimiento", "No funcional", "Soporte", "Informes", "Notificaciones", "Seguridad"} == northstar
    assert {row["component"] for row in dashboard(locale="es")["requirements"]} <= set(rows.values())


def test_scope_draft_components_follow_the_locale() -> None:
    text = "- Customers can download invoices as PDF\n"
    client.post(f"{ACME}/scope/extract", files={"file": ("amendment.txt", text.encode(), "text/plain")})
    english = client.get(f"{ACME}/scope/versions").json()[0]["diff"]["added"][0]["component"]
    spanish = client.get(f"{ACME}/scope/versions?locale=es").json()[0]["diff"]["added"][0]["component"]
    assert english == "Billing"
    assert spanish == "Facturación"

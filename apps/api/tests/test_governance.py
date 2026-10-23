"""Edge cases for verification, privacy policy, retention and evidence."""
import base64
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException  # noqa: F401
from fastapi.testclient import TestClient

from app.domain import calculate_readiness
from app.file_inspector import inspect_file
from app.main import app, get_evidence_object
from app.providers import MockLLMProvider
from app.security import DataClassification, PrivacyPolicy, classify_text, redact_sensitive
from app.storage import LocalStorageProvider

client = TestClient(app)


class _ExternalProvider:
    provider_name = "hosted-a"


def test_verification_judge_requires_observations():
    provider = MockLLMProvider()
    demonstrated = provider.judge_result([{"summary": "Export button downloaded the CSV"}])
    empty = provider.judge_result([])
    plan = provider.plan_verification({"text": "The CSV contains the filtered rows"})
    assert demonstrated["state"] == "demonstrated"
    assert empty["state"] == "inconclusive"
    assert plan["provider"] == "BrowserAgent"
    assert plan["steps"]
    assert provider.classify_bug_or_change("Scope v1", "Please review the wording")["classification"] == "needs_human_review"


def test_verification_run_marks_known_gaps_and_skips_unknown_ids():
    requirements = client.get("/api/v1/projects/project_demo/requirements").json()
    by_human = {item["human_id"]: item["id"] for item in requirements}
    response = client.post(
        "/api/v1/projects/project_demo/runs",
        json={"requirement_ids": [by_human["REQ-001"], by_human["REQ-010"], "missing-requirement"], "target_url": "https://demo.example"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["target_url"] == "https://demo.example"
    states = {item["requirement_id"]: item["state"] for item in body["evidence"]}
    assert states[by_human["REQ-001"]] == "demonstrated"
    assert states[by_human["REQ-010"]] == "not_demonstrated"
    assert by_human["REQ-001"] in {item["source_id"] for item in client.get("/api/v1/projects/project_demo/graph").json()["relationships"]}


def test_reference_requirement_without_evidence_stays_not_demonstrated():
    response = client.post("/api/v1/projects/project_acme/runs", json={"requirement_ids": ["REQ-071"]})
    assert response.status_code == 200
    assert response.json()["evidence"][0]["state"] == "not_demonstrated"


def test_file_inspector_rejects_bad_payloads_without_failing_the_request():
    broken = client.post(
        "/api/v1/projects/project_demo/file-inspections",
        json={"filename": "broken.json", "content_base64": base64.b64encode(b"{").decode()},
    )
    assert broken.status_code == 200
    assert broken.json()["valid"] is False
    assert broken.json()["assessment"] == "partially_demonstrated"
    assert "File could not be parsed" == broken.json()["error"]

    mismatch = client.post(
        "/api/v1/projects/project_demo/file-inspections",
        json={
            "filename": "orders.csv",
            "content_base64": base64.b64encode(b"id,status\n1,open\n").decode(),
            "expected_columns": ["id", "status", "owner"],
            "expected_row_count": 4,
        },
    )
    assert mismatch.json()["assessment"] == "partially_demonstrated"
    assert mismatch.json()["checks"] == {"columns_match": False, "row_count_match": False}

    unsupported = inspect_file("payload.bin", b"not-a-document")
    assert unsupported["valid"] is False
    assert client.post(
        "/api/v1/projects/project_demo/file-inspections",
        json={"filename": "orders.csv", "content_base64": "not base64!!!"},
    ).status_code == 400


def test_bug_report_without_a_baseline_signal_stays_with_a_human():
    response = client.post(
        "/api/v1/projects/project_demo/bug-change-assessment",
        json={"report": "Can someone look at the wording of the introduction?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "needs_human_review"
    assert body["requires_human_confirmation"] is True
    assert body["compared_scope_version"] == "v1"


def test_readiness_score_stays_inside_bounds_for_empty_and_penalised_sets():
    empty = calculate_readiness([], [], [])
    assert empty.score == 0
    assert empty.pending_acceptance == 0
    penalised = calculate_readiness(
        [{"id": "1", "status": "not_demonstrated"}],
        [],
        [{"status": "proposed"}] * 8,
        unresolved_comments=9,
    )
    assert 0 <= penalised.score <= 100
    assert penalised.without_evidence == 1
    assert penalised.unapproved_scope_changes == 8


def test_policy_blocks_unapproved_providers_and_over_classified_data():
    policy = PrivacyPolicy()
    with pytest.raises(HTTPException) as unapproved:
        policy.assert_allowed(type("PrivateModel", (), {"provider_name": "self-hosted"})(), DataClassification.INTERNAL, True)
    assert unapproved.value.status_code == 403

    with pytest.raises(HTTPException) as restricted:
        policy.assert_allowed(_ExternalProvider(), DataClassification.HIGHLY_CONFIDENTIAL, True)
    assert restricted.value.status_code == 403

    with pytest.raises(HTTPException) as consent:
        policy.assert_allowed(_ExternalProvider(), DataClassification.CONFIDENTIAL, False)
    assert consent.value.status_code == 428

    policy.assert_allowed(_ExternalProvider(), DataClassification.CONFIDENTIAL, True)
    policy.assert_allowed(MockLLMProvider(), DataClassification.RESTRICTED, False)


def test_invalid_classification_ceiling_falls_back_to_confidential(monkeypatch):
    monkeypatch.setenv("SDA_AI_MAX_EXTERNAL_CLASSIFICATION", "not-a-level")
    policy = PrivacyPolicy()
    assert policy.max_external_classification is DataClassification.CONFIDENTIAL


def test_redaction_covers_keys_and_can_keep_contact_data():
    secret = "bearer " + ("a" * 16)
    safe, categories = redact_sensitive(f"token={secret} payroll@example.com")
    assert secret not in safe
    assert "payroll@example.com" not in safe
    assert categories == ["pii", "secret"]
    secrets_only, secret_categories = redact_sensitive("password=local-only user@example.com", redact_pii=False)
    assert "local-only" not in secrets_only
    assert "user@example.com" in secrets_only
    assert secret_categories == ["secret"]
    assert classify_text("medical record attached") is DataClassification.HIGHLY_CONFIDENTIAL
    assert classify_text("Approved delivery narrative") is DataClassification.INTERNAL


def test_retention_windows_ignore_blank_and_invalid_values(monkeypatch):
    monkeypatch.setenv("SDA_DOCUMENT_RETENTION_DAYS", "14")
    monkeypatch.setenv("SDA_EVIDENCE_RETENTION_DAYS", "-3")
    monkeypatch.setenv("SDA_PORTAL_LINK_RETENTION_DAYS", "soon")
    monkeypatch.setenv("SDA_LLM_METADATA_RETENTION_DAYS", "")
    body = client.get("/api/v1/projects/project_demo/privacy/retention").json()
    assert body == {
        "document_retention_days": 14,
        "evidence_retention_days": 0,
        "portal_link_days": 7,
        "llm_metadata_retention_days": 730,
        "raw_prompts_stored": False,
    }
    assert client.get("/api/v1/projects/missing/privacy/retention").status_code == 404


def test_document_erasure_removes_content_and_keeps_audit_metadata_only():
    uploaded = client.post("/api/v1/scope/import", files={"file": ("agreement.txt", b"Approved baseline", "text/plain")})
    document_id = uploaded.json()["document_id"]
    assert uploaded.json()["retention_days"] >= 0
    erased = client.delete(f"/api/v1/projects/project_demo/documents/{document_id}")
    assert erased.status_code == 200
    assert client.delete(f"/api/v1/projects/project_demo/documents/{document_id}").status_code == 404
    audit = client.get("/api/v1/projects/project_demo/audit").json()
    event = next(item for item in audit if item.get("event") == "document_erased" and item.get("document_id") == document_id)
    assert "filename" not in event
    assert "sha256" not in event
    assert "Approved baseline" not in str(event)


def test_low_classification_does_not_need_a_document_consent():
    response = client.post(
        "/api/v1/projects/project_demo/ai/consents",
        json={
            "document_id": "doc_public",
            "provider": "hosted-a",
            "model_or_route": "default",
            "classification": "INTERNAL",
            "purpose": "demo extraction",
        },
    )
    assert response.status_code == 422


def test_signed_evidence_rejects_tampering_expiry_and_traversal(tmp_path):
    storage = LocalStorageProvider(root=str(tmp_path), secret="test-secret")
    storage.put_object("runs/login-success.png", b"png-bytes", "image/png")
    url = storage.get_signed_url("runs/login-success.png", expires_seconds=60)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    expires = int(query["expires"][0])
    signature = query["signature"][0]
    assert storage.verify_signed_url("runs/login-success.png", expires, signature)
    assert storage.verify_signed_url("runs/login-success.png", expires, "0" + signature) is False
    assert storage.verify_signed_url("runs/login-success.png", 1, signature) is False
    for unsafe in ("../secret", "/etc/passwd", "runs/../../secret", "runs//hidden"):
        with pytest.raises(ValueError):
            storage.get_signed_url(unsafe)

    evidence = client.get("/api/v1/projects/project_demo/evidence").json()[0]
    signed = client.get(f"/api/v1/projects/project_demo/evidence/{evidence['artifact']}/signed-url").json()["url"]
    assert client.get(signed).status_code == 200
    assert client.get(signed.replace("signature=", "signature=0", 1)).status_code == 403
    assert client.get("/api/v1/evidence/missing-artifact", params={"expires": 1, "signature": "abc"}).status_code == 403
    with pytest.raises(HTTPException) as traversal:
        get_evidence_object("../secret", 4_000_000_000, "abc")
    assert traversal.value.status_code == 400


def test_privacy_policy_response_does_not_echo_secrets():
    body = client.get("/api/v1/projects/project_demo/privacy-policy").json()
    assert body["requires_consent"] is True
    assert "mock" in body["allowed_providers"]
    rendered = str(body).lower()
    assert "api_key" not in rendered
    assert "secret" not in rendered

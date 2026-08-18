from app.security import DataClassification, PrivacyPolicy, classify_text, redact_sensitive
from app.providers import MockLLMProvider
from app.storage import LocalStorageProvider
from app.main import AITaskRequest


def test_redacts_credentials_and_pii_before_model_processing():
    safe, categories = redact_sensitive("api_key=secret-value contact test@example.com +34 600 111 222")
    assert "secret-value" not in safe
    assert "test@example.com" not in safe
    assert "secret" in categories
    assert "pii" in categories


def test_classification_is_conservative_for_restricted_content():
    assert classify_text("password=super-secret") == DataClassification.RESTRICTED
    assert classify_text("A normal delivery agreement with a date 2026-01-01") == DataClassification.CONFIDENTIAL


def test_mock_provider_is_safe_for_local_confidential_demo():
    policy = PrivacyPolicy()
    policy.assert_allowed(MockLLMProvider(), DataClassification.RESTRICTED, consent=False)


def test_storage_rejects_path_traversal():
    storage = LocalStorageProvider(root="/tmp/sda-security-test")
    try:
        storage.get_signed_url("../../etc/passwd")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal key was accepted")


def test_ai_request_accepts_human_readable_classification():
    request = AITaskRequest(task="extract_scope", classification="CONFIDENTIAL")
    assert request.classification is DataClassification.CONFIDENTIAL

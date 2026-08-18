"""Security and privacy policy primitives for tenant-owned content.

This module deliberately contains policy decisions, not provider-specific code.
Keeping them here makes it possible to enforce the same rules for OpenAI,
OpenRouter, private models and future verification providers.
"""
from __future__ import annotations

import os
import re
from enum import IntEnum
from typing import Any

from fastapi import HTTPException


class DataClassification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    HIGHLY_CONFIDENTIAL = 3
    RESTRICTED = 4


class PrivacyPolicy:
    """Tenant-independent baseline policy, configurable by deployment."""

    def __init__(self) -> None:
        configured = os.getenv("SDA_AI_ALLOWED_PROVIDERS", "mock,openai")
        self.allowed_providers = {item.strip().lower() for item in configured.split(",") if item.strip()}
        self.require_consent = os.getenv("SDA_AI_REQUIRE_CONSENT", "true").lower() == "true"
        self.redact_before_ai = os.getenv("SDA_AI_REDACT_BEFORE_PROCESSING", "true").lower() == "true"
        self.max_external_classification = DataClassification[
            os.getenv("SDA_AI_MAX_EXTERNAL_CLASSIFICATION", "CONFIDENTIAL").upper()
        ]

    def provider_name(self, provider: Any) -> str:
        name = getattr(provider, "provider_name", None) or provider.__class__.__name__
        if name.lower().endswith("provider"):
            name = name[:-8]
        return name.lower()

    def assert_allowed(self, provider: Any, classification: DataClassification, consent: bool) -> None:
        name = self.provider_name(provider)
        if name not in self.allowed_providers:
            raise HTTPException(403, f"AI provider '{name}' is not approved by the organization policy")
        if classification > self.max_external_classification and name != "mock":
            raise HTTPException(403, "This data classification requires a private AI provider")
        if self.require_consent and name != "mock" and not consent:
            raise HTTPException(428, "Explicit consent is required before sending confidential content to AI")


# Common credential and personal-data patterns. These are intentionally
# conservative: false positives are preferable to leaking a secret to a model.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}"),
)
_PII_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)"),
)


def redact_sensitive(text: str, *, redact_pii: bool = True) -> tuple[str, list[str]]:
    """Return safe model input and categories that were redacted."""
    redacted = text
    categories: list[str] = []
    for pattern in _SECRET_PATTERNS:
        redacted, count = pattern.subn("[REDACTED_SECRET]", redacted)
        if count:
            categories.append("secret")
    if redact_pii:
        for pattern in _PII_PATTERNS:
            redacted, count = pattern.subn("[REDACTED_PII]", redacted)
            if count:
                categories.append("pii")
    return redacted, sorted(set(categories))


def classify_text(text: str) -> DataClassification:
    """Conservative content classification used before an external AI call."""
    lowered = text.lower()
    if any(marker in lowered for marker in ("private key", "password=", "api_key", "bearer ")):
        return DataClassification.RESTRICTED
    if any(marker in lowered for marker in ("salary", "bank account", "medical record", "passport")):
        return DataClassification.HIGHLY_CONFIDENTIAL
    if "@" in text or any(char.isdigit() for char in text):
        return DataClassification.CONFIDENTIAL
    return DataClassification.INTERNAL

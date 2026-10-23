"""Domain contracts for the Agreement-to-Acceptance delivery graph.

The mock API uses these contracts today; the PostgreSQL repositories can adopt
them without changing the product-facing API.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

VerificationState = Literal["demonstrated", "partially_demonstrated", "not_demonstrated", "inconclusive", "manual_review_required"]
ChangeClassification = Literal["clarification", "possible_scope_change", "already_included", "contradiction", "ambiguous", "unknown"]
ChangeStatus = Literal["proposed", "estimated", "approved", "rejected", "incorporated"]


class SourceTrace(BaseModel):
    document_id: str
    page: Optional[int] = None
    section: Optional[str] = None
    quote: str
    confidence: float = Field(ge=0, le=1)


class EvidenceRelationship(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: Literal["supports", "implements", "verifies", "contains", "accepted_by", "changed_by"]


class DeliveryReadiness(BaseModel):
    total_requirements: int
    implemented: int
    demonstrated: int
    partial: int
    not_demonstrated: int
    without_evidence: int
    unapproved_scope_changes: int
    unresolved_comments: int
    accepted: int
    pending_acceptance: int
    score: int = Field(ge=0, le=100)


class BugChangeAssessment(BaseModel):
    classification: Literal["likely_defect", "likely_change_request", "ambiguous", "needs_human_review"]
    confidence: float = Field(ge=0, le=1)
    reason: str
    compared_scope_version: str
    related_requirement_ids: list[str] = Field(default_factory=list)
    requires_human_confirmation: bool = True


def calculate_readiness(requirements: list[dict], evidence: list[dict], changes: list[dict], unresolved_comments: int = 0, accepted: int = 0) -> DeliveryReadiness:
    total = len(requirements)
    demonstrated = sum(r.get("status") == "demonstrated" for r in requirements)
    partial = sum(r.get("status") == "partially_demonstrated" for r in requirements)
    not_demo = sum(r.get("status") == "not_demonstrated" for r in requirements)
    implemented = sum(r.get("implementation_status", "implemented") == "implemented" for r in requirements)
    evidence_ids = {str(e.get("requirement_id")) for e in evidence}
    without_evidence = sum(str(r.get("id")) not in evidence_ids for r in requirements)
    unapproved = sum(c.get("status") in {"proposed", "estimated"} for c in changes)
    pending = max(total - accepted, 0)
    raw = 0 if total == 0 else round(((demonstrated + partial * 0.5) / total) * 100)
    penalty = min(25, unapproved * 5 + without_evidence * 2 + unresolved_comments * 3)
    return DeliveryReadiness(total_requirements=total, implemented=implemented, demonstrated=demonstrated, partial=partial, not_demonstrated=not_demo, without_evidence=without_evidence, unapproved_scope_changes=unapproved, unresolved_comments=unresolved_comments, accepted=accepted, pending_acceptance=pending, score=max(0, min(100, raw - penalty)))

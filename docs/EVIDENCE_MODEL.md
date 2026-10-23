# Evidence model

Evidence is part of a delivery graph, not an untyped attachment collection:

`Agreement → ScopeVersion → Requirement → AcceptanceCriterion → DeliveryReference → VerificationRun → EvidenceArtifact → DeliveryRelease → AcceptanceDecision`

Artifacts carry a hash, content type, source, timestamp, creator and relationship metadata. Local mock links are HMAC signed with an absolute expiry; production S3/R2 links are presigned. Retention policies belong to the storage adapter and are not inferred from a delivery readiness score.

## Creating evidence

A verification run creates an `Evidence` record per requirement with its state (`demonstrated`, `partially_demonstrated`, `not_demonstrated`, `inconclusive`), the steps that produced it, the artifact name and a SHA-256. In the functional demo project it also adds an `EvidenceRelationship` of type `verifies` from the requirement to the evidence. QA explorer runs store their observations as `agent-runs/{run_id}/qa-observations.json` with the hash of the stored content. `GET /api/v1/projects/{id}/graph` returns scope versions, requirements and evidence as nodes, their relationships, and how many requirements have no evidence yet.

## Opening evidence

```mermaid
sequenceDiagram
  participant UI as Workspace
  participant API as FastAPI
  participant Store as Storage adapter
  UI->>API: GET /projects/{id}/evidence/{artifact}/signed-url
  API->>Store: get_signed_url(key, 900 s)
  Store->>Store: Normalize key, reject traversal
  Store->>Store: HMAC-SHA256(secret, key:expires)
  Store-->>API: /api/v1/evidence/{key}?expires&signature
  API-->>UI: Signed URL
  UI->>API: GET /api/v1/evidence/{key}?expires&signature
  API->>Store: verify_signed_url(key, expires, signature)
  alt Expired or signature mismatch
    API-->>UI: 403 link expired or invalid
  else Unsafe key
    API-->>UI: 400 unsafe evidence key
  else Valid
    Store-->>API: Object bytes
    API-->>UI: 200 application/octet-stream
  end
```

The local adapter (`LocalStorageProvider` in `apps/api/app/storage.py`) signs `key:expires` with `SDA_STORAGE_SECRET`, clamps the lifetime between 1 second and 24 hours and compares signatures with `hmac.compare_digest`. Keys that are absolute, empty or contain `.`, `..` or `//` segments are rejected before any file access. `S3StorageProvider` stores the SHA-256 as object metadata and returns presigned URLs with the same lifetime limits.

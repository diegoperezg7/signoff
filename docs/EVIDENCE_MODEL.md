# Evidence model

Evidence is part of a delivery graph, not an untyped attachment collection:

`Agreement → ScopeVersion → Requirement → AcceptanceCriterion → DeliveryReference → VerificationRun → EvidenceArtifact → DeliveryRelease → AcceptanceDecision`

Artifacts carry a hash, content type, source, timestamp, creator and relationship metadata. Local mock links are HMAC signed with an absolute expiry; production S3/R2 links are presigned. Retention policies belong to the storage adapter and are not inferred from a delivery readiness score.

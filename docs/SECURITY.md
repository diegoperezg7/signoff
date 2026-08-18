# Security

Tenant isolation is enforced at the API boundary for the canonical project catalog: organization comes from the authenticated user and the PostgreSQL adapter filters by organization. Mock mode uses the deterministic demo principal. Production mode requires a bearer token, a verified Supabase JWT with `sub`, `exp` and an explicit organization claim, and membership validation in the persistence layer.

Local evidence links are HMAC signed with an absolute expiry and the S3/R2 adapter delegates expiry to presigned URLs. Storage keys reject absolute paths and traversal segments. Secret/PII redaction, provider allowlists, consent, host allowlists, isolated browser contexts, file validation, CSP, rate limiting and audit events remain required controls before accepting real client data.

The browser agent treats all visited content as untrusted. Destructive actions are disabled by default and sensitive actions require explicit confirmation. The current demo uses mock data and must not receive real secrets. OpenAI requests isolate external content from system instructions, use structured outputs and request `store=false`; retention and provider policy must still be reviewed for the deployment region and data classification.

# Data retention

The application stores document and evidence metadata separately from binary
content. Production storage must use an S3-compatible bucket with encryption,
lifecycle rules and signed URLs. Local storage is development-only.

Recommended defaults:

- original documents and evidence: 365 days;
- portal links: 7 days unless explicitly extended;
- LLM metadata: 24 months;
- prompts and raw model responses: disabled by default;
- audit events: configurable by organization and protected from ordinary edits.

Deletion workflows must remove originals, extracted text, redacted text,
derived artifacts and delivery exports, then record a non-sensitive audit event.

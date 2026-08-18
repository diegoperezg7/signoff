# Data classification

SDA treats every uploaded agreement as `CONFIDENTIAL` by default. Classification
is a safety control, not a legal determination.

| Level | Default AI behavior |
| --- | --- |
| PUBLIC | Approved external providers allowed |
| INTERNAL | Approved external providers allowed |
| CONFIDENTIAL | Consent, redaction and approved provider required |
| HIGHLY_CONFIDENTIAL | Private/enterprise provider required |
| RESTRICTED | External AI blocked; human or private processing only |

Credentials, cookies, API keys and private keys are always redacted or blocked
before model processing. Original documents remain in tenant-owned storage and
are never written to application logs.

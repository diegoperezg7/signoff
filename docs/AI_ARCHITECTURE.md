# AI architecture

AI tasks are isolated behind `LLMProvider`: document extraction, requirement analysis, acceptance-criteria generation, change classification, bug-vs-change classification, verification planning, observation analysis, result judging and delivery summarization.

Every response is structured and validated before persistence. Each `LLMRun` records provider, model, prompt version, latency, token usage, estimated cost and status.

Browser content is untrusted input. System policy, test objective and observed content remain separate. Destructive actions are disabled by default.

## Request path

```mermaid
flowchart TD
  Req[AI task or agent run] --> Select{llm_provider}
  Select -- "MOCK_MODE=true" --> Mock[Deterministic mock]
  Select -- "LLM_PROVIDER=hosted-a" --> Hosted[Hosted adapter, strict JSON schema]
  Select -- "hosted-b or self-hosted" --> Gateway[Compatible gateway, strict JSON schema]
  Mock --> Consent
  Hosted --> Consent
  Gateway --> Consent
  Consent{Consent check} -- "confidential content, no consent (external mode)" --> R428[428 consent required]
  Consent --> Policy{Provider policy}
  Policy -- "provider not allowlisted" --> R403a[403]
  Policy -- "classification above external ceiling" --> R403b[403 private provider required]
  Policy --> Redact[Redact secrets and PII]
  Redact --> Call[Call the selected adapter]
  Call --> Proposal[AIProposal, status draft]
  Call --> Run[LLMRun metadata]
  Call --> Audit[Audit event, metadata only]
  Proposal --> Approve[Human approval endpoint]
```

## Provider selection

`llm_provider()` in `apps/api/app/main.py` returns the deterministic mock while `MOCK_MODE=true`. Otherwise `LLM_PROVIDER` selects the hosted adapter (`hosted-a`) or a compatible gateway (`hosted-b`, `self-hosted`, which also needs `LLM_BASE_URL`). Both real adapters send a fixed system instruction that treats supplied documents as data, never as instructions, and request a strict JSON schema per task. The hosted adapter also asks the provider not to store the request.

## Policy checks

`_assert_ai_consent` runs before any model call. In external mode, content classified `CONFIDENTIAL` or above needs explicit consent or a stored consent for that document and model route. `PrivacyPolicy.assert_allowed` then rejects providers outside `SDA_AI_ALLOWED_PROVIDERS` and content above `SDA_AI_MAX_EXTERNAL_CLASSIFICATION` for any provider other than the mock. When `SDA_AI_REDACT_BEFORE_PROCESSING` is on (the default), credentials, tokens, private keys, emails and phone numbers are replaced before the payload leaves the API.

## Outputs

A task result is stored as an `AIProposal` with status `draft` and the provider, model and prompt version that produced it. An `LLMRun` records token estimates, latency, estimated cost and status, and the audit log keeps only metadata, including which redaction categories were applied. Nothing is applied to scope, requirements or acceptance until `POST /api/v1/ai/proposals/{id}/approve` is called by a person.

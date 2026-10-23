# AI provider policy

Signoff sends model work through one gateway. API keys stay on the server.
Every request records the provider id, model id, policy snapshot, classification,
consent state, latency, token metadata and outcome on an `LLMRun`. Prompts and
raw responses are not stored by default.

`SDA_AI_ALLOWED_PROVIDERS` is the deployment allowlist. The default is
`mock,hosted-a`.

| Provider id | Role |
| --- | --- |
| `mock` | Deterministic local provider used by the demo and CI. No document content leaves the process. |
| `hosted-a` | Hosted LLM that must return structured JSON. Allowed for data at or below the configured ceiling. |
| `hosted-b` | Optional hosted gateway. Add it only after the route, residency and retention terms are accepted. |
| `self-hosted` | Private model reached through `LLM_BASE_URL`. Use this for data that must not leave the organization. |

External processing requires explicit consent and cannot exceed
`SDA_AI_MAX_EXTERNAL_CLASSIFICATION` (default `CONFIDENTIAL`). An unrecognized
ceiling falls back to `CONFIDENTIAL`. Data above the ceiling needs a private
provider.

Hosted requests ask the provider not to retain the payload where the API
supports that option. That is not a promise of zero retention. Abuse monitoring
and account-level settings still follow the provider contract. Verify those
terms before sending confidential project data.

For highly confidential or restricted documents, point `LLM_PROVIDER` at
`self-hosted`, set `LLM_BASE_URL` to the private endpoint, and narrow the
allowlist to that provider id.

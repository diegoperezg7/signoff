# AI provider policy

SDA uses an AI gateway. API keys are server-side only. Every request records
provider, model, policy snapshot, classification, consent state, latency, token
metadata and outcome in `LLMRun`; prompts and raw responses are not logged by
default.

The deployment allowlist is controlled by `SDA_AI_ALLOWED_PROVIDERS`. The
default is `mock,openai`. External processing requires explicit consent and
cannot process data above `SDA_AI_MAX_EXTERNAL_CLASSIFICATION` (default:
`CONFIDENTIAL`).

OpenAI requests use `store=false` where supported. This is not a promise of
zero retention: provider abuse monitoring and endpoint-specific application
state are governed by the provider contract. OpenRouter is only suitable when
the selected route is explicitly approved and its ZDR policy has been verified.

For highly confidential or restricted documents, configure a private provider
and set `SDA_AI_ALLOWED_PROVIDERS` accordingly.

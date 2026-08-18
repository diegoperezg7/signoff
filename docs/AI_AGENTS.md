# Signoff contextual agents

Signoff exposes agents inside the active project and release workspace. They are
task-specific operators, not a general-purpose chat assistant.

## Agents

| Agent | Purpose | Tools |
| --- | --- | --- |
| Delivery analyst | Explain readiness, blockers and next decision | readiness, attention, delivery summary |
| Requirements coach | Review a requirement and draft atomic criteria | requirement inspection, requirement analysis, criteria generation |
| Verification planner | Select a bounded verification approach | requirement inspection, verification planning |
| Change radar | Explain change signals that need human review | attention, change classification |
| Agreement analyst | Find commitments, ambiguities and missing criteria | scope inspection, requirement listing, requirement analysis |
| QA explorer | Check an allowed running app and capture smoke observations | requirement inspection, route discovery, smoke check |
| Evidence curator | Find weak or missing evidence | evidence listing, readiness, attention |
| Acceptance assistant | Prepare a client-ready summary without deciding for them | readiness, evidence, delivery summary |

## Tool boundary and runtime

Each agent receives a finite plan and an allowlist of tools. Tool execution is
performed by the API, never directly by the browser or by model-generated
code. The registry in `apps/api/app/agent_runtime.py` is the single source of
truth for tool risk, category, schemas and side effects. A plan is rejected if
the tool is not in both the agent allowlist and the organization policy.

Every run is a resumable state machine with an `AgentRunRecord`, one
`AgentStep` per tool call and an `AgentCheckpoint` after every successful
step. The mock adapter keeps these records in memory; the PostgreSQL schema
and Alembic migration use the same shape for production workers.

Any proposal that could change product data is stored as a draft `AIProposal`
and must be approved through the existing approval endpoint. Side-effecting
tools additionally create `AgentApproval` records. Hard-risk acceptance
decisions are never automatically executed, even in `max_autonomy` mode.
Every run records the tenant, project, agent, provider, model, classification,
tool names, checkpoints, duration and audit event.

The default `max_autonomy` policy means read and proposal tools can run without
interrupting the user. Writes, external sends and acceptance decisions remain
approval-gated. Owners and admins can narrow the policy, block tools, lower
step limits or disable external models at `/api/v1/agent-policy`.

## Privacy

The agent endpoint uses the same classification, consent and redaction policy
as the existing AI task endpoint. Mock mode is safe for local development and
CI. In external mode, confidential processing requires explicit consent and
the configured provider policy. Credentials, tokens, passwords and PII are
redacted before model processing where configured.

## API

- `GET /api/v1/agents`
- `GET /api/v1/agent-tools`
- `GET/PATCH /api/v1/agent-policy`
- `POST /api/v1/projects/{project_id}/agents/dispatch`
- `POST /api/v1/projects/{project_id}/agents/run`
- `POST /api/v1/projects/{project_id}/intelligence/ask`
- `GET /api/v1/projects/{project_id}/agents/runs`
- `GET /api/v1/agent-runs/{run_id}`
- `POST /api/v1/agent-runs/{run_id}/cancel`
- `POST /api/v1/agent-runs/{run_id}/resume`
- `GET /api/v1/agent-runs/{run_id}/approvals`
- `POST /api/v1/agent-runs/{run_id}/email-alert`
- `POST /api/v1/agent-approvals/{approval_id}`
- `POST /api/v1/ai/proposals/{proposal_id}/approve`

The frontend dock shows the selected agent, its tools, the execution trace and
the approval state so the user can understand what happened before accepting
the result.

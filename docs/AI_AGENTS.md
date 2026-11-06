# Signoff contextual agents

Signoff exposes agents inside the active project and release workspace. They are
task-specific operators, not a general-purpose chat assistant.

## Agents

| Agent | Purpose | Tools |
| --- | --- | --- |
| Delivery analyst | Explain readiness, blockers and next decision | readiness, attention, delivery summary |
| Requirements coach | Review a requirement and draft atomic criteria | requirement inspection, requirement analysis, criteria generation |
| Verification planner | Select a bounded verification approach | requirement inspection, verification planning |
| Change radar | Classify a request against the baseline and draft it as a change | attention, change classification |
| Agreement analyst | Find commitments, ambiguities and missing criteria | scope inspection, requirement listing, requirement analysis |
| QA explorer | Check an allowed running app and capture smoke observations | requirement inspection, route discovery, smoke check |
| Evidence curator | Find weak or missing evidence | evidence listing, readiness, attention |
| Acceptance assistant | Prepare a client-ready summary without deciding for them | readiness, evidence, delivery summary |

## Tool boundary and runtime

Each agent receives a finite plan and an allowlist of tools. Tool execution is
performed by the API, never directly by the browser or by model-generated
code. The registry in `apps/api/app/agent_runtime.py` is the single source of
truth for tool risk, category, schemas and side effects. Every step of the plan
is authorized before the run is queued: if a tool is not in both the agent
allowlist and the organization policy, `POST /agents/run` answers 403 and no
run is created.

Tools read the live project facts through `apps/api/app/agent_tools.py`: the
readiness score, attention items, the selected requirement with its criteria,
evidence and open comments, the active baseline and the user's request. The
same requirement gives the same result, and a different request or state gives
a different one. When no requirement is given, the agent works on the one that
most needs attention.

## Run lifecycle

`POST /api/v1/projects/{project_id}/agents/run` (or `/agents/dispatch`, which
picks the agent from the request text) returns at once with
`{run_id, agent, status: "queued"}`. The plan then runs on a background thread:

`queued` → `running` → `requires_approval` → `completed`, or `failed` at any step.

Every run is a resumable state machine with an `AgentRunRecord`, one
`AgentStep` per tool call and an `AgentCheckpoint` after every successful
step. The mock adapter keeps these records in memory; the PostgreSQL schema
and Alembic migration use the same shape for production workers. Any error
(a blocked host in the QA explorer, a provider error, a missing requirement)
ends the run as `failed` with a `run_failed` event; it never becomes a 500.
The audit event of a finished run carries the run's own id.

## Event stream

`GET /api/v1/agent-runs/{run_id}/events?locale=en|es` is a Server-Sent Events
stream (`text/event-stream`). Each event is `id: <n>`, `event: <type>` and a
JSON `data` line, with ids starting at 1 and increasing by one.

| Event | Data |
| --- | --- |
| `run_started` | `run_id`, `agent {id, name}`, `requirement_id`, `steps [{index, tool, label}]` |
| `step_started` | `index`, `tool`, `label` |
| `step_completed` | `index`, `tool`, `label`, `duration_ms`, `summary`, `refs [{type, id, label}]` |
| `proposal_created` | `proposal` |
| `run_completed` | `status`, `summary`, `proposal_id` |
| `run_failed` | `error` |

Step indexes start at 0. The stream replays from a position with the
`Last-Event-ID` header or `?after=<n>`, and ends after `run_completed` or
`run_failed`. The web panel reads it with `fetch` and a `ReadableStream`, so it
can send an authorization header outside mock mode. Labels and summaries are
localized by the `locale` parameter.

In mock mode each step takes 0.4 to 0.9 seconds so the progress is visible.
`SIGNOFF_AGENT_STEP_DELAY` fixes the delay in seconds (the tests use `0`), and
`SIGNOFF_RUN_DELAY` sets the latency of a verification run (default 1.2).

## Proposals

Every successful run ends with exactly one draft proposal and the status
`requires_approval`.

| Agent | Proposal kind | Approving it |
| --- | --- | --- |
| Requirements coach | `criteria` (`before`, `after`) | Replaces the requirement's criteria with `after` (source `agent`) and clears a known defect, so the next verification can pass |
| Verification planner | `verification_plan` (`steps`) | Stores the plan on the requirement |
| QA explorer | `evidence` (`artifact`, `summary`, `state`, `observations`) | Creates an evidence item (source `agent`) and sets the requirement's verification from its state |
| Change radar | `change` (`title`, `original`, `proposed`, `classification`, `impact`) | Creates a change request with status `proposed` and the next `CHG-` code |
| Agreement analyst | `comments` (`items [{requirement_id, text}]`) | Adds the comments, authored by the agent; they count as open comments |
| Evidence curator, Delivery analyst, Acceptance assistant | `report` (`sections`, `refs`) | Nothing is applied; approving acknowledges the report |

`POST /api/v1/projects/{project_id}/proposals/{id}/approve` applies the
proposal and returns `{proposal, applied: [refs]}`.
`POST .../proposals/{id}/reject` (optional `comment`) changes nothing else.
Both mark the run `completed` and write an activity entry. The legacy
`POST /api/v1/ai/proposals/{id}/approve` uses the same apply logic.

Side-effecting tools additionally create `AgentApproval` records. Hard-risk
acceptance decisions are never automatically executed, even in `max_autonomy`
mode. Every run records the tenant, project, agent, provider, model,
classification, tool names, checkpoints, duration and audit event.

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
- `GET /api/v1/agent-runs/{run_id}/events`
- `GET /api/v1/projects/{project_id}/proposals?status=draft`
- `POST /api/v1/projects/{project_id}/proposals/{proposal_id}/approve`
- `POST /api/v1/projects/{project_id}/proposals/{proposal_id}/reject`
- `POST /api/v1/agent-runs/{run_id}/cancel`
- `POST /api/v1/agent-runs/{run_id}/resume`
- `GET /api/v1/agent-runs/{run_id}/approvals`
- `POST /api/v1/agent-runs/{run_id}/email-alert`
- `POST /api/v1/agent-approvals/{approval_id}`
- `POST /api/v1/ai/proposals/{proposal_id}/approve`

The agent panel shows each step as pending, running or done with its duration
and a readable summary, links to the requirements, evidence and changes it
touched, and the final proposal with Approve and Reject. Pending proposals also
appear in the release's attention items and notifications, so they are visible
outside the panel.

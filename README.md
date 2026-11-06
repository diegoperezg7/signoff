<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/brand/signoff-lockup-dark.png">
    <img src="apps/web/public/brand/signoff-lockup-light.png" alt="Signoff, software delivery assurance" width="320">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/diegoperezg7/signoff/actions/workflows/ci.yml"><img src="https://github.com/diegoperezg7/signoff/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white" alt="Next.js 16">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19">
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 16">
  <img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white" alt="Redis 7">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-All%20rights%20reserved-blue.svg" alt="All rights reserved"></a>
</p>

<p align="center">Prove what was agreed, what changed, what was delivered and what the client accepted.</p>

Signoff is a browser workspace for software delivery assurance. It keeps the path from an agreement to client acceptance in one trace, without replacing the tracker, the repository or the test suite a team already uses.

<p align="center">
  <img src="docs/images/walkthrough.gif" alt="Walkthrough from the project list through an agent run and a change approval to client acceptance" width="920">
</p>

## Screens

Every screen is captured in light and dark mode from the app in mock mode. The full set lives in [`docs/screenshots/`](docs/screenshots), one file per screen and theme (`NN-screen-light.png`, `NN-screen-dark.png`). GitHub shows the version that matches your theme.

**1. Release overview.** Requirements, verification, coverage and change counts for the active release, with the selected requirement in the side drawer.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/01-dashboard-overview-dark.png">
  <img src="docs/screenshots/01-dashboard-overview-light.png" alt="Release overview" width="920">
</picture>

**2. Requirements.** Requirements from the approved baseline, with status, owner and acceptance criteria. Generated criteria are stored as a proposal, not applied.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/02-requirements-dark.png">
  <img src="docs/screenshots/02-requirements-light.png" alt="Requirements" width="920">
</picture>

**3. Changes.** Change signals compared with the baseline; a person approves or rejects each one before it enters the release.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/03-changes-dark.png">
  <img src="docs/screenshots/03-changes-light.png" alt="Changes" width="920">
</picture>

**4. Verification.** A bounded run per requirement reports criteria covered and refreshes the linked evidence.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/04-verification-dark.png">
  <img src="docs/screenshots/04-verification-light.png" alt="Verification" width="920">
</picture>

**5. Evidence.** Every artifact is traced to its requirement and opened through a signed, expiring link.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/05-evidence-dark.png">
  <img src="docs/screenshots/05-evidence-light.png" alt="Evidence" width="920">
</picture>

**6. Sign-off.** Readiness checks before the delivery pack is sent to the client.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/06-signoff-dark.png">
  <img src="docs/screenshots/06-signoff-light.png" alt="Sign-off" width="920">
</picture>

**7. Agent panel.** Eight task-specific agents work inside the active release. Write actions always require approval.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/07-agents-dark.png">
  <img src="docs/screenshots/07-agents-light.png" alt="Agent panel" width="920">
</picture>

**8. Projects.** Both demo workspaces, each with its client, release status and requirement count.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/08-projects-dark.png">
  <img src="docs/screenshots/08-projects-light.png" alt="Projects" width="920">
</picture>

**9. Milestones.** Milestones and target dates for each release.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/09-milestones-dark.png">
  <img src="docs/screenshots/09-milestones-light.png" alt="Milestones" width="920">
</picture>

**10. Releases.** Release inventory with current state, coverage and next milestone.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/10-releases-dark.png">
  <img src="docs/screenshots/10-releases-light.png" alt="Releases" width="920">
</picture>

**11. Reports.** Delivery report and evidence pack exports.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/11-reports-dark.png">
  <img src="docs/screenshots/11-reports-light.png" alt="Reports" width="920">
</picture>

**12. Baselines.** Approved scope baselines; a new document is extracted into a draft until someone confirms it.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/12-baselines-dark.png">
  <img src="docs/screenshots/12-baselines-light.png" alt="Baselines" width="920">
</picture>

**13. Metrics.** Coverage, verification and acceptance from one source.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/13-metrics-dark.png">
  <img src="docs/screenshots/13-metrics-light.png" alt="Metrics" width="920">
</picture>

**14. Risk.** Prioritized attention across changes, evidence and acceptance.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/14-risk-dark.png">
  <img src="docs/screenshots/14-risk-light.png" alt="Risk" width="920">
</picture>

**15. Templates.** Reusable structures to start a traceable delivery.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/15-templates-dark.png">
  <img src="docs/screenshots/15-templates-light.png" alt="Templates" width="920">
</picture>

**16. Teams.** People and roles in the organization.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/16-teams-dark.png">
  <img src="docs/screenshots/16-teams-light.png" alt="Teams" width="920">
</picture>

**17. Integrations.** Manual references and verification providers.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/17-integrations-dark.png">
  <img src="docs/screenshots/17-integrations-light.png" alt="Integrations" width="920">
</picture>

**18. Settings.** Language (ES/EN) and theme (light, dark or system).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/18-settings-dark.png">
  <img src="docs/screenshots/18-settings-light.png" alt="Settings" width="920">
</picture>

**19. Client review portal.** The client opens a tokenized link with the delivery story and the evidence index, and accepts or requests a revision. No workspace account is needed.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/19-review-portal-dark.png">
  <img src="docs/screenshots/19-review-portal-light.png" alt="Client review portal" width="920">
</picture>

### Workflow states

**20. Baseline draft.** After uploading an amendment, the extracted requirements appear as a draft version to review before confirming it into the baseline.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/20-baseline-draft-dark.png">
  <img src="docs/screenshots/20-baseline-draft-light.png" alt="Baseline draft" width="920">
</picture>

**21. Agent at work.** The agent panel streams each step as it runs: done steps show their duration, summary and the requirement they touched.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/21-agent-running-dark.png">
  <img src="docs/screenshots/21-agent-running-light.png" alt="Agent running" width="920">
</picture>

**22. Agent proposal.** Every run ends with a proposal pending review; approving it applies the change to the project.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/22-agent-proposal-dark.png">
  <img src="docs/screenshots/22-agent-proposal-light.png" alt="Agent proposal" width="920">
</picture>

## AI agents

Agents are task-specific operators bound to the active project and release, not a general chat assistant. Each one has a finite plan and an allowlist of tools; the API executes the tools, never the browser or model-generated code.

| Icon | Agent | What it does | Tools |
| --- | --- | --- | --- |
| `Route` | Delivery analyst | Explains what is blocking the release and the next decision. | `get_delivery_readiness`, `list_attention_items`, `summarize_delivery` |
| `ListChecks` | Requirements coach | Proposes atomic, testable acceptance criteria for one requirement. | `inspect_requirement`, `analyze_requirement`, `generate_acceptance_criteria` |
| `ClipboardCheck` | Verification planner | Turns a requirement into a bounded verification plan. | `inspect_requirement`, `plan_verification` |
| `GitCompareArrows` | Change radar | Explains which change signals need human review. | `list_attention_items`, `classify_change` |
| `FileSearch` | Agreement analyst | Finds commitments, ambiguities and missing criteria in the baseline. | `inspect_scope`, `list_requirements`, `analyze_requirement` |
| `MonitorCheck` | QA explorer | Checks an allowed running app and stores the observations as evidence. | `inspect_requirement`, `plan_verification`, `discover_routes`, `run_smoke_check` |
| `FolderCheck` | Evidence curator | Finds missing, stale or weak evidence. | `list_evidence`, `get_delivery_readiness`, `list_attention_items` |
| `Stamp` | Acceptance assistant | Prepares a client-ready summary without deciding for the client. | `get_delivery_readiness`, `list_evidence`, `summarize_delivery` |

Every tool in `apps/api/app/agent_runtime.py` declares a risk level (`read`, `propose`, `write`, `execute`, `external`, `critical`). A step runs only if the tool is in the agent allowlist and the organization policy allows its risk. The default policy is `max_autonomy`: read and proposal tools run without interruption, while `write`, `execute` and `external` tools create an approval record. Acceptance decisions are never executed by an agent.

Runs are asynchronous. The API answers with a queued run, executes the plan on a background thread and streams each step over Server-Sent Events. Tools read the live project facts, and every run ends with one draft proposal that changes nothing until a person approves it.

```mermaid
sequenceDiagram
  actor User
  participant Dock as Agent panel
  participant API as FastAPI
  participant Worker as Background run
  participant Policy as Tool registry and policy
  participant Store as Project store
  User->>Dock: Choose agent and ask
  Dock->>API: POST /projects/{id}/agents/run
  API->>API: Consent, redaction, build_plan
  API->>Policy: authorize every planned tool
  Policy-->>API: allowed (else 403, no run)
  API->>Worker: start run
  API-->>Dock: run_id, status queued
  Dock->>API: GET /agent-runs/{run_id}/events (SSE)
  loop Each planned step
    Worker->>Store: Read live facts (readiness, requirement, evidence)
    Worker->>Store: AgentStep and AgentCheckpoint
    API-->>Dock: step_started, step_completed (summary, refs)
  end
  Worker->>Store: Proposal (draft), run requires_approval
  API-->>Dock: proposal_created, run_completed
  Dock-->>User: Proposal to review
  User->>API: POST /projects/{id}/proposals/{proposal_id}/approve
  API->>Store: Apply (criteria, plan, evidence, change or comments)
  API->>Store: Run completed, audit event
  API-->>Dock: proposal and applied refs
```

See [Contextual agents](docs/AI_AGENTS.md) and [AI architecture](docs/AI_ARCHITECTURE.md).

## Technical highlights

- **Organization isolation.** Outside mock mode, the user and organization come from a verified Supabase access token (JWKS RS256, or HS256 with the project secret), and the membership table is authoritative for the role. Every route under `/api/v1/projects/{project_id}` resolves the project through the caller's organization before the handler runs, so a project, agent run, approval or AI consent from another organization returns 404, and the PostgreSQL repository filters every project query by `organization_id`.
- **HMAC-signed evidence links.** Evidence is stored with its SHA-256. Local links are signed with HMAC-SHA256 over `key:expiry`, last 15 minutes by default (24 hours at most), are compared in constant time and reject path traversal. In production the S3/R2 adapter issues presigned URLs instead.
- **Data classification and AI consent.** Content is classified on five levels (`PUBLIC` to `RESTRICTED`). An AI call is allowed only for an allowlisted provider, below the configured ceiling for external processing, and with explicit consent for confidential content, recorded per document and model route. Secrets and personal data are redacted before model calls by default. Mock mode never sends content off the machine.
- **Draft-first AI.** Every model output is stored as a proposal with provider, model, prompt version, tokens, latency and estimated cost, and changes nothing until a person approves it.
- **Tests.** 65 API tests (`make test`) cover the verification engine, readiness scoring, the agent runtime and policy, the event stream, redaction, consent, retention, signed links, the review flow, and the coherence of every view after each user action. CI also builds the Next.js app.

## Architecture

```mermaid
flowchart LR
  subgraph browser [Browser]
    Workspace[Project workspace]
    Portal[Client review portal]
  end
  subgraph services [Services]
    API[FastAPI]
    Worker[Background worker]
  end
  Workspace --> API
  Portal --> API
  API --> Policy[Privacy policy]
  API --> Verify[Verification engine]
  Verify --> Evidence[Signed evidence]
  API --> DB[(PostgreSQL)]
  API --> Queue[(Redis)]
  Worker --> Queue
```

Mock mode keeps the project store in memory and uses a deterministic local model, so the demo and CI need no external keys. Production mode uses the same API with PostgreSQL, a worker, object storage and an allowlisted model provider. See [Architecture](docs/ARCHITECTURE.md) and [AI provider policy](docs/AI_PROVIDER_POLICY.md).

### How it fits together

Each project has one store that holds facts only: requirements, criteria, evidence, verification runs, changes, comments, baselines, client decisions, agent proposals and audit events. Every view is a projection of those facts, computed on each read: dashboard metrics and charts, attention items, notifications, activity, readiness, delivery checks and the client's story. An action changes a fact once, and every section reflects it on the next read; the web app invalidates the shared queries after each mutation.

- **Baseline:** upload a document, review the extracted draft and its diff, confirm it to add, update or retire requirements.
- **Agent criteria:** the requirements coach streams its steps and drafts criteria as a proposal; approving it replaces the criteria.
- **Verification:** a run records evidence per requirement, updates its status and adds a point to the coverage trend.
- **Evidence upload:** attach a file to a requirement; CSV, JSON and XLSX files are inspected and the result is shown.
- **Changes:** approving a change agrees its requirements; rejecting it moves them out of scope.
- **Comments:** comments persist per requirement, count against readiness while open and are resolved in place.
- **Delivery:** prepare shows live checks, send for acceptance marks the release ready, and the client accepts, rejects or requests a revision in the portal.

## Repository layout

```text
signoff/
├── apps/
│   ├── api/                    FastAPI service
│   │   ├── app/
│   │   │   ├── main.py         HTTP routes and the delivery flow
│   │   │   ├── seed.py         Coherent bilingual facts for both demo projects
│   │   │   ├── projections.py  Every read model, derived from the facts
│   │   │   ├── catalog.py      Facade over the store and projections
│   │   │   ├── agents.py       The eight agents and their tool plans
│   │   │   ├── agent_tools.py  Tool execution on live facts and proposal building
│   │   │   ├── agent_runtime.py  Tool registry, risk levels, policy, runs and checkpoints
│   │   │   ├── providers.py    LLM provider contract, mock and hosted adapters
│   │   │   ├── security.py     Data classification, provider policy and redaction
│   │   │   ├── storage.py      Hashed evidence storage and signed links (local, S3/R2)
│   │   │   ├── auth.py         Token validation and organization membership
│   │   │   ├── domain.py       Readiness scoring and evidence relationships
│   │   │   ├── file_inspector.py  CSV, JSON, TXT and XLSX inspection
│   │   │   ├── qa_explorer.py  Route discovery and smoke checks on allowed hosts
│   │   │   ├── db.py, persistence.py  SQLAlchemy models and PostgreSQL repository
│   │   │   └── jobs.py         Inline job runner for mock mode
│   │   ├── migrations/         Alembic migrations
│   │   └── tests/              pytest suite
│   ├── web/                    Next.js workspace and client review portal
│   │   ├── app/                Routes and stylesheets
│   │   ├── components/
│   │   │   ├── dashboard/      Workspace, overview, charts, drawer, tab views
│   │   │   └── agents/         Agent panel with the streamed run timeline
│   │   ├── lib/
│   │   │   ├── api.ts          Typed API client, query keys and invalidation
│   │   │   └── queries.ts      react-query hooks for reads and mutations
│   │   └── public/             Brand assets
│   └── worker/                 Dramatiq actors for Redis deployments
├── docs/                       Architecture, policies and design system
│   └── screenshots/            Every screen in light and dark mode
├── docker-compose.yml          API, web, worker, PostgreSQL and Redis
└── Makefile                    api, web, up, test, lint, migrate
```

## Project status

Signoff is a proof of concept.

- **Mock mode is the default.** Both projects live in one in-memory store that resets on restart, the model is a deterministic local provider and every request acts as the demo owner. No external keys are needed.
- **Verification is simulated but consistent.** A run's outcome follows from the facts: a requirement without criteria or with a known defect fails until a change or new criteria fix it, and every run stores evidence with its SHA-256. The file inspector and uploaded evidence are real. The QA explorer makes real HTTP requests, only to allowed local hosts, and falls back to simulated observations in mock mode when the app is not running.
- **Agents run in-process.** Mock runs use a background thread and are paced for the demo; they do not survive an API restart.
- **The worker is a stub.** The Dramatiq actors in `apps/worker` record job state transitions but do not run browsers or models yet.
- **Production adapters exist but are not the demo path:** PostgreSQL repository and migrations, Supabase token validation, S3/R2 storage, hosted model adapters and email delivery. A few legacy routes addressed by resource id instead of project (`PATCH /api/v1/requirements/{id}`, `POST /api/v1/requirements/{id}/criteria`, `PATCH /api/v1/changes/{id}`, `POST /api/v1/scope/import`) look the resource up across the demo projects and are not organization-scoped yet.

## Quickstart

Docker Compose runs the API, web app, worker, PostgreSQL and Redis. The compose file uses local placeholder credentials only.

```bash
cp .env.example .env
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000); it goes straight to the dashboard. The review portals are `/review/acme-review-token` and `/review/demo-review-token`. The API reference is [http://localhost:8000/docs](http://localhost:8000/docs).

Without Docker, from a machine with Python 3.12 and Node 20. Mock mode is the default, so no database, Redis or API keys are needed.

```bash
# Terminal 1: API on http://localhost:8000
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt
make api
```

```bash
# Terminal 2: web app on http://localhost:3000
make web
```

The web app reads the API address from `NEXT_PUBLIC_SDA_API_URL` (default `http://127.0.0.1:8000`). The API only accepts browser requests from ports 3000 and 4100 on `localhost` and `127.0.0.1`. Agent runs are paced at 0.4 to 0.9 seconds per step; set `SIGNOFF_AGENT_STEP_DELAY` (seconds) to change it and `SIGNOFF_RUN_DELAY` for verification latency.

## Tests

```bash
make test
make lint
```

`make test` runs the API suite with the `python3` on your path (override with `make test PYTHON=...`). `make lint` byte-compiles the API and runs ESLint on the web app. The web job in CI builds the Next.js app.

## Governance

- [Data classification](docs/DATA_CLASSIFICATION.md)
- [Data retention](docs/DATA_RETENTION.md)
- [AI provider policy](docs/AI_PROVIDER_POLICY.md)
- [Evidence model](docs/EVIDENCE_MODEL.md)
- [Verification engine](docs/VERIFICATION_ENGINE.md)
- [Security](docs/SECURITY.md)
- [AI architecture](docs/AI_ARCHITECTURE.md) · [Contextual agents](docs/AI_AGENTS.md)
- [Product](docs/PRODUCT.md) · [Roadmap](docs/ROADMAP.md) · [Design system](docs/DESIGN_SYSTEM.md)

Hosted and self-hosted models are selected by provider id (`hosted-a`, `hosted-b`, `self-hosted`). The demo never sends project content to an external model.

## License

Proprietary. Copyright (c) 2026 Diego Pérez. All rights reserved.

See [LICENSE](LICENSE). The source may be viewed for evaluation only. Production use, copying, modification and redistribution require prior written permission.

# Implementation status

## Implemented consolidation

- FastAPI API with a canonical project/release catalog for Acme Inc. and Customer Operations Portal.
- Next.js workspace with one shared shell, release tabs, global routes and URL-synchronised project/release/requirement context.
- Mock acceptance criteria generation and simulated browser verification.
- Client review routes at `/review/demo-review-token` and `/review/acme-review-token`, resolved by token rather than a hardcoded project.
- Docker Compose, environment template, API tests, CI workflow and product/security/architecture documentation.

## Product reorientation implemented

- Added `PRODUCT_REORIENTATION.md` with the audit and migration strategy.
- Added domain contracts for readiness, evidence relationships and bug-vs-change classification.
- Added File Inspector support for CSV, JSON, TXT and optional XLSX parsing.
- Added scope version endpoints, extraction result, readiness, prepare-delivery checks, evidence graph, human evidence, acceptance decisions, audit and intelligence endpoints.
- Added SQLAlchemy models for identity, scope, requirements, criteria, changes, verification, evidence, delivery packs, comments, integrations and audit events.
- Added a PostgreSQL repository adapter and startup seed path for `MOCK_MODE=false`; `InMemoryRepository` remains deterministic for demo and CI.
- Added signed local evidence links with expiration and an S3/R2 adapter shape.
- Added full `LLMProvider` parity, structured `OpenAIProvider`, mock proposals, approval endpoint and cost telemetry.
- Added Dramatiq actors for scope extraction, AI tasks, verification, file inspection and delivery-pack generation.
- Removed the legacy dashboard implementation from `apps/web/app/page.tsx`; `/` is landing only.
- Added global routes: Projects, Milestones, Releases, Reports, Baselines, Metrics, Risk, Templates, Teams, Integrations and Settings.
- Unified functional project endpoints for both demos: requirements, changes, scope versions, runs, evidence, readiness, graph, acceptance, attention and delivery pack now resolve from the active project/release context.
- Added PostgreSQL canonical IDs and persisted projection metadata so mock and production adapters expose the same public contracts.
- Completed the core client journey in the shared release tabs: generate criteria, decide Change Radar items, run verification, inspect CSV evidence, open signed artifacts, prepare delivery and send the selected release to client review.
- Acceptance decisions now write an audit event and update the Customer Operations release projection so the client action is visible back in the workspace.
- Added deterministic demo evidence fallback objects and zero-size-safe Recharts measurement so signed evidence opens locally and charts stay clean during responsive layout changes.

## Remaining production increments

1. Finish replacing legacy mutation endpoints with domain routers backed by PostgreSQL repositories.
2. Complete Supabase JWKS/RS256 validation and organization membership management.
3. Connect browser workers to isolated Playwright contexts, allowlists and artifact uploads.
4. Add production PDF/DOCX extraction, PDF/ZIP renderers, rate limiting and external telemetry.
5. Add Jira, Linear, GitHub, CI ingestion and API verification adapters.

# Software Delivery Assurance

SDA is the operating system for proving software delivery. It connects Agreement, Build, Change, Verify, Evidence and Accept without replacing Jira, GitHub or existing QA tools.

## Run locally

Requirements: Python 3.11+ and Node 20.9+.

```bash
make up              # full stack: API, web, worker, Postgres and Redis
```

For a lightweight mock-only loop, run `make api` and `make web` in separate terminals.

Then open [http://localhost:3000](http://localhost:3000). SDA is a browser-based SaaS: no desktop download is required. The public landing lives at `/`; select **Open demo workspace** to enter `/dashboard`. The workspace has two shared-architecture demos: `Acme Inc. / Release 2.3` for the visual sign-off state and `Customer Operations Portal v1 / Release 1.0` for the functional flow. The client-facing review portals are available at `/review/acme-review-token` and `/review/demo-review-token`. The API is available at [http://localhost:8000/docs](http://localhost:8000/docs).

The default `MOCK_MODE=true` requires no external keys. Both demo projects are seeded deterministically in the mock catalog on startup. Set `NEXT_PUBLIC_SDA_API_URL` at web build time to point the browser at another API. With `MOCK_MODE=false`, the API initializes the SQLAlchemy/PostgreSQL catalog, validates Supabase-style JWTs signed with `SUPABASE_JWT_SECRET`, uses `OpenAIProvider` when `OPENAI_API_KEY` is configured and can use S3/R2 through the storage adapter.

## Useful commands

```bash
make api       # FastAPI development server
make web       # Next.js development server
make test      # API tests
make lint      # Python compile check and frontend lint
```

This repository contains the consolidated product flow: public landing, shared multi-project workspace, project/release URL context, agreement extraction mock, frozen scope versions, requirements and acceptance criteria, interactive Change Radar, Verification Engine boundary, File Inspector, Evidence Graph, Delivery Readiness, downloadable Delivery Pack, tokenized client review portal, structured AI proposals, signed evidence links and cost telemetry.

## Brand system

The Signoff identity is available in reusable light/dark lockups and mark variants under `apps/web/public/brand`. The interface uses the source palette: Primary `#6366F1`, Indigo `#4F46E5`, Deep `#312E81`, Navy `#0F172A`, Slate `#1E1E2E`, Gray `#94A3B8`, Light `#F8FAFC` and White `#FFFFFF`. The app includes a persistent light/dark theme switch, App Router favicon, Apple icon and web manifest.

## Production notes

Set `MOCK_MODE=false`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `DATABASE_URL`, `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` and a non-default `SDA_STORAGE_SECRET` in the deployment environment. For confidential data, review `SDA_AI_ALLOWED_PROVIDERS`, `SDA_AI_REQUIRE_CONSENT`, `SDA_AI_REDACT_BEFORE_PROCESSING` and `SDA_AI_MAX_EXTERNAL_CLASSIFICATION`; the defaults require consent, redact PII/secrets and block data above `CONFIDENTIAL` for external providers. Keep `SDA_JOB_MODE=inline` for local mock work or route long-running work through the Dramatiq worker with Redis. The persistence, AI and storage boundaries are documented in `docs/ARCHITECTURE.md`, `docs/AI_ARCHITECTURE.md`, `docs/DATA_CLASSIFICATION.md`, `docs/AI_PROVIDER_POLICY.md` and `docs/DATA_RETENTION.md`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [Product](docs/PRODUCT.md) · [Security](docs/SECURITY.md)
- [AI architecture](docs/AI_ARCHITECTURE.md) · [Verification Engine](docs/VERIFICATION_ENGINE.md) · [Evidence model](docs/EVIDENCE_MODEL.md)
- [Roadmap](docs/ROADMAP.md) · [Implementation plan](PLAN.md) · [Product reorientation](PRODUCT_REORIENTATION.md)

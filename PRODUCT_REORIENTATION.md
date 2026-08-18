# Product reorientation audit

## Current state

Signoff has a consolidated SaaS workspace: a Next.js landing and shared dashboard shell, FastAPI project/release projections, two deterministic demo projects, requirements, evidence, Change Radar, Delivery Pack and tokenized client review routes. The legacy dashboard was removed from `apps/web/app/page.tsx`; the landing is now the only `/` experience. Mock mode uses an in-memory catalog, while production mode can initialize the PostgreSQL repository.

## Product direction

Signoff is the operating system for proving software delivery. Its core trace is:

`Agreement → Build → Change → Verify → Evidence → Accept`

Verification is a mechanism inside this trace, not the category of the product.

## Reuse and migration

- Preserve the current demo seed and mock provider behavior.
- Keep `DemoStore` only as a compatibility fixture behind repository/provider contracts.
- Initialize PostgreSQL with tenant-aware repositories and Alembic models.
- Use one shared shell and canonical project/release context for Projects, Releases, Baselines, Metrics, Risk, Reports and release tabs.
- Keep Agreement, Scope, Delivery, Evidence, Acceptance and Intelligence as concepts inside Baselines, Releases/Reports, Sign-off/Portal and Metrics/Risk rather than duplicate top-level products.
- Use structured AI proposals and approval rather than an unconstrained chat surface.
- Add File Inspector, Scope Versioning, Delivery Readiness and Evidence Relationships before external integrations.

## Out of scope

Generic Kanban, sprint planning, time tracking, CRM, generic bug tracking, IDE behavior and a general-purpose test suite.

## Risks

- Browser verification may be unreliable on complex applications.
- Scope extraction needs human confirmation and source citations.
- The product must avoid turning readiness scores into legal conclusions.
- Real integrations require per-provider permissions and retry policies.
